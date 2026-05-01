"""Unit tests for aesthetic scoring backends."""

from __future__ import annotations

import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch import nn

from photos_pipeline.config import Settings, get_settings
from photos_pipeline.modules.scoring import (
    DEFAULT_SCORER_CLIP_MODEL_NAME,
    IMAGENET_MEAN,
    IMAGENET_STD,
    MODEL_INPUT_SIZE,
    CLIPScorer,
    CLIPScorerLoadError,
    CLIPScorerUnavailableError,
    NIMAScorer,
    ScorerWeightsDownloadError,
    ScorerWeightsLoadError,
    build_nima_model,
    create_scorer,
    expected_scores_from_model_output,
    load_nima_model,
    resolve_device,
    resolve_weights_path,
)
from photos_pipeline.modules.scoring.backend import (
    _ImageNetPreprocessor,
    _TransformersClipBackend,
    load_clip_backend,
)


class _FakeNIMAModel(nn.Module):
    def __init__(self, outputs: list[torch.Tensor]) -> None:
        super().__init__()
        self._outputs = outputs
        self.batch_shapes: list[tuple[int, ...]] = []

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        self.batch_shapes.append(tuple(inputs.shape))
        return self._outputs.pop(0)


class _FakeClipBackend:
    def score_batch(self, images: list[np.ndarray], *, device: torch.device) -> list[float]:
        return [float(index + 1) for index, _ in enumerate(images)]


class _FakeClipProcessor:
    def __call__(
        self,
        *,
        text: list[str] | None = None,
        images: list[object] | None = None,
        return_tensors: str,
        padding: bool = False,
        truncation: bool = False,
    ) -> dict[str, torch.Tensor]:
        assert return_tensors == "pt"
        assert padding is (text is not None)
        assert truncation is (text is not None)

        if text is not None:
            values = [
                1.0 if "beautiful" in prompt or "stunning" in prompt else -1.0
                for prompt in text
            ]
            return {"input_ids": torch.tensor(values, dtype=torch.float32).unsqueeze(1)}

        assert images is not None
        means = [float(np.asarray(image, dtype=np.float32).mean() / 255.0) for image in images]
        return {"pixel_values": torch.tensor(means, dtype=torch.float32).unsqueeze(1)}


class _FakeClipModel:
    def __init__(self) -> None:
        self.batch_shapes: list[tuple[int, ...]] = []
        self.device = torch.device("cpu")

    def eval(self) -> _FakeClipModel:
        return self

    def to(self, device: torch.device) -> _FakeClipModel:
        self.device = device
        return self

    def get_text_features(self, *, input_ids: torch.Tensor) -> torch.Tensor:
        return torch.cat([input_ids, torch.zeros_like(input_ids)], dim=1).to(self.device)

    def get_image_features(self, *, pixel_values: torch.Tensor) -> torch.Tensor:
        self.batch_shapes.append(tuple(pixel_values.shape))
        coordinates = pixel_values.squeeze(1).mul(2.0).sub(1.0)
        orthogonal = torch.sqrt(torch.clamp(1.0 - coordinates.square(), min=0.0))
        return torch.stack([coordinates, orthogonal], dim=1).to(self.device)


class _FakeClipFeatureOutput:
    def __init__(self, embeddings: torch.Tensor) -> None:
        self.pooler_output = embeddings


class _FakeStructuredClipModel(_FakeClipModel):
    def get_text_features(self, *, input_ids: torch.Tensor) -> _FakeClipFeatureOutput:
        return _FakeClipFeatureOutput(super().get_text_features(input_ids=input_ids))

    def get_image_features(self, *, pixel_values: torch.Tensor) -> _FakeClipFeatureOutput:
        return _FakeClipFeatureOutput(super().get_image_features(pixel_values=pixel_values))


def _install_fake_transformers(
    monkeypatch: pytest.MonkeyPatch,
    *,
    model_factory: Callable[[str], _FakeClipModel] | None = None,
    processor_factory: Callable[[str], _FakeClipProcessor] | None = None,
) -> tuple[list[str], list[str]]:
    model_calls: list[str] = []
    processor_calls: list[str] = []

    class _FakeTransformersClipModelLoader:
        @staticmethod
        def from_pretrained(model_name: str) -> _FakeClipModel:
            model_calls.append(model_name)
            if model_factory is not None:
                return model_factory(model_name)
            return _FakeClipModel()

    class _FakeTransformersClipProcessorLoader:
        @staticmethod
        def from_pretrained(model_name: str) -> _FakeClipProcessor:
            processor_calls.append(model_name)
            if processor_factory is not None:
                return processor_factory(model_name)
            return _FakeClipProcessor()

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            CLIPModel=_FakeTransformersClipModelLoader,
            CLIPProcessor=_FakeTransformersClipProcessorLoader,
        ),
    )
    return model_calls, processor_calls


@pytest.mark.unit
def test_resolve_device_auto_prefers_available_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

    assert resolve_device("auto").type == "cuda"


@pytest.mark.unit
def test_resolve_device_auto_falls_back_to_cpu_when_cuda_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    assert resolve_device("auto").type == "cpu"


@pytest.mark.unit
def test_preprocessor_normalises_rgb_images() -> None:
    image = np.full((320, 400, 3), 255, dtype=np.uint8)

    batch = _ImageNetPreprocessor().preprocess_batch([image])

    assert batch.shape == (1, 3, 224, 224)
    assert batch[0, 0, 0, 0].item() == pytest.approx((1.0 - IMAGENET_MEAN[0]) / IMAGENET_STD[0])
    assert batch[0, 1, 0, 0].item() == pytest.approx((1.0 - IMAGENET_MEAN[1]) / IMAGENET_STD[1])
    assert batch[0, 2, 0, 0].item() == pytest.approx((1.0 - IMAGENET_MEAN[2]) / IMAGENET_STD[2])


@pytest.mark.unit
def test_expected_scores_accept_logits_or_probabilities() -> None:
    probabilities = torch.tensor([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]])
    logits = torch.tensor([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 8.0]])

    assert expected_scores_from_model_output(probabilities) == [10.0]
    assert expected_scores_from_model_output(logits)[0] == pytest.approx(9.9802, rel=1e-3)


@pytest.mark.unit
def test_nima_scorer_batches_inference(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_model = _FakeNIMAModel(
        outputs=[
            torch.tensor(
                [
                    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                    [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                ],
                dtype=torch.float32,
            ),
            torch.tensor([[0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]], dtype=torch.float32),
        ]
    )
    weights_path = tmp_path / "nima_weights.pth"
    weights_path.write_bytes(b"stub")

    monkeypatch.setattr(
        "photos_pipeline.modules.scoring.backend.resolve_weights_path",
        lambda configured_path, _: configured_path,
    )
    monkeypatch.setattr(
        "photos_pipeline.modules.scoring.backend.load_nima_model",
        lambda *_args, **_kwargs: fake_model,
    )

    scorer = NIMAScorer(
        weights_path=weights_path,
        weights_url="https://example.invalid/nima_weights.pth",
        batch_size=2,
        device="cpu",
    )
    image = np.full((300, 300, 3), 128, dtype=np.uint8)

    scores = scorer.score_batch([image, image, image])

    assert scores == [10.0, 1.0, 5.0]
    assert fake_model.batch_shapes == [(2, 3, 224, 224), (1, 3, 224, 224)]


@pytest.mark.unit
def test_resolve_weights_path_downloads_missing_file(tmp_path: Path) -> None:
    weights_path = tmp_path / "models" / "nima_weights.pth"

    def downloader(url: str, destination: Path) -> None:
        assert url == "https://example.invalid/nima_weights.pth"
        destination.write_bytes(b"weights")

    resolved = resolve_weights_path(
        weights_path,
        "https://example.invalid/nima_weights.pth",
        downloader=downloader,
    )

    assert resolved == weights_path
    assert weights_path.read_bytes() == b"weights"


@pytest.mark.unit
def test_resolve_weights_path_cleans_partial_download(tmp_path: Path) -> None:
    weights_path = tmp_path / "models" / "nima_weights.pth"

    def downloader(_url: str, destination: Path) -> None:
        destination.write_bytes(b"partial")
        raise RuntimeError("network broke")

    with pytest.raises(ScorerWeightsDownloadError):
        resolve_weights_path(
            weights_path,
            "https://example.invalid/nima_weights.pth",
            downloader=downloader,
        )

    assert not weights_path.exists()
    assert not weights_path.with_suffix(f"{weights_path.suffix}.download").exists()


@pytest.mark.unit
def test_load_nima_model_round_trips_state_dict(tmp_path: Path) -> None:
    weights_path = tmp_path / "nima_weights.pth"
    torch.save(build_nima_model().state_dict(), weights_path)

    model = load_nima_model(weights_path, torch.device("cpu"))

    assert isinstance(model, nn.Module)
    assert model.training is False


@pytest.mark.slow
def test_nima_cpu_batch_throughput_stays_under_one_second_per_image(tmp_path: Path) -> None:
    weights_path = tmp_path / "nima_weights.pth"
    torch.save(build_nima_model().state_dict(), weights_path)

    scorer = NIMAScorer(
        weights_path=weights_path,
        weights_url="https://example.invalid/nima_weights.pth",
        batch_size=16,
        device="cpu",
    )
    base_image = np.full((MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 3), 128, dtype=np.uint8)
    images = [base_image.copy() for _ in range(scorer.batch_size)]

    scorer.score_batch(images)

    per_image_timings: list[float] = []
    for _ in range(3):
        start = time.perf_counter()
        scores = scorer.score_batch(images)
        elapsed = time.perf_counter() - start
        assert len(scores) == len(images)
        per_image_timings.append(elapsed / len(images))

    median_per_image = statistics.median(per_image_timings)
    print(
        f"NIMA CPU per-image timings: {[round(timing, 4) for timing in per_image_timings]} "
        f"(median={median_per_image:.4f}s)"
    )
    assert median_per_image < 1.0


@pytest.mark.unit
def test_nima_scorer_uses_environment_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    synthetic_thumbnail_factory,
) -> None:
    fake_model = _FakeNIMAModel(
        outputs=[
            torch.tensor([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]], dtype=torch.float32)
        ]
    )
    env_weights_path = tmp_path / "env-models" / "nima_weights.pth"
    captured: dict[str, object] = {}

    def fake_resolve(configured_path: Path, configured_url: str) -> Path:
        captured["resolved_path"] = configured_path
        captured["resolved_url"] = configured_url
        env_weights_path.parent.mkdir(parents=True, exist_ok=True)
        env_weights_path.write_bytes(b"stub")
        return env_weights_path

    def fake_load(weights_path: Path, device: torch.device) -> _FakeNIMAModel:
        captured["loaded_path"] = weights_path
        captured["loaded_device"] = device
        return fake_model

    monkeypatch.setenv("PHOTOS_PIPELINE_SCORER_WEIGHTS_PATH", str(env_weights_path))
    monkeypatch.setenv("PHOTOS_PIPELINE_SCORER_WEIGHTS_URL", "https://example.invalid/env-nima.pth")
    monkeypatch.setenv("PHOTOS_PIPELINE_SCORER_BATCH_SIZE", "3")
    monkeypatch.setenv("PHOTOS_PIPELINE_SCORER_DEVICE", "cpu")
    monkeypatch.setattr("photos_pipeline.modules.scoring.backend.resolve_weights_path", fake_resolve)
    monkeypatch.setattr("photos_pipeline.modules.scoring.backend.load_nima_model", fake_load)
    get_settings.cache_clear()

    try:
        scorer = NIMAScorer()
        score = scorer.score(synthetic_thumbnail_factory(192))
    finally:
        get_settings.cache_clear()

    assert scorer.batch_size == 3
    assert scorer.device.type == "cpu"
    assert scorer.weights_path == env_weights_path
    assert captured["resolved_path"] == env_weights_path
    assert captured["resolved_url"] == "https://example.invalid/env-nima.pth"
    assert captured["loaded_path"] == env_weights_path
    assert captured["loaded_device"] == torch.device("cpu")
    assert score == 7.0
    assert fake_model.batch_shapes == [(1, 3, 224, 224)]


@pytest.mark.unit
def test_load_nima_model_rejects_hdf5_checkpoint(tmp_path: Path) -> None:
    weights_path = tmp_path / "nima_weights.pth"
    weights_path.write_bytes(b"\x89HDF\r\n\x1a\npayload")

    with pytest.raises(ScorerWeightsLoadError, match="HDF5/Keras"):
        load_nima_model(weights_path, torch.device("cpu"))


@pytest.mark.unit
def test_zero_shot_clip_backend_scores_images_and_batches(synthetic_scoring_references) -> None:
    backend = _TransformersClipBackend(
        model_name=DEFAULT_SCORER_CLIP_MODEL_NAME,
        model=_FakeClipModel(),
        processor=_FakeClipProcessor(),
        batch_size=2,
    )
    reference_images = [reference.image for reference in synthetic_scoring_references]

    scores = backend.score_batch(reference_images, device=torch.device("cpu"))

    assert scores == pytest.approx(
        [reference.expected_clip_score for reference in synthetic_scoring_references],
        abs=0.05,
    )
    assert backend._model.batch_shapes == [(2, 1), (1, 1)]


@pytest.mark.unit
def test_zero_shot_clip_backend_accepts_structured_model_outputs() -> None:
    backend = _TransformersClipBackend(
        model_name=DEFAULT_SCORER_CLIP_MODEL_NAME,
        model=_FakeStructuredClipModel(),
        processor=_FakeClipProcessor(),
        batch_size=2,
    )

    scores = backend.score_batch(
        [
            np.zeros((32, 32, 3), dtype=np.uint8),
            np.full((32, 32, 3), 255, dtype=np.uint8),
        ],
        device=torch.device("cpu"),
    )

    assert scores[0] < 2.0
    assert scores[1] > 9.9


@pytest.mark.unit
def test_load_clip_backend_builds_transformers_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    model_calls, processor_calls = _install_fake_transformers(monkeypatch)

    backend = load_clip_backend(model_name="test/clip-model", batch_size=2)
    scores = backend.score_batch(
        [
            np.zeros((32, 32, 3), dtype=np.uint8),
            np.full((32, 32, 3), 255, dtype=np.uint8),
        ],
        device=torch.device("cpu"),
    )

    assert isinstance(backend, _TransformersClipBackend)
    assert scores[0] < 2.0
    assert scores[1] > 9.9
    assert model_calls == ["test/clip-model"]
    assert processor_calls == ["test/clip-model"]


@pytest.mark.unit
def test_load_clip_backend_surfaces_model_load_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_loader(_model_name: str) -> _FakeClipModel:
        raise RuntimeError("boom")

    _install_fake_transformers(monkeypatch, model_factory=fail_loader)

    with pytest.raises(CLIPScorerLoadError, match="Failed to load CLIP scorer model 'test/clip'"):
        load_clip_backend(model_name="test/clip", batch_size=2)


@pytest.mark.unit
def test_clip_scorer_surfaces_loader_unavailable_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_loader(*, model_name: str, batch_size: int) -> _FakeClipBackend:
        raise CLIPScorerUnavailableError(f"missing backend for {model_name} ({batch_size})")

    monkeypatch.setattr("photos_pipeline.modules.scoring.backend.load_clip_backend", fake_loader)

    with pytest.raises(CLIPScorerUnavailableError, match="missing backend"):
        CLIPScorer(device="cpu", batch_size=2, model_name="test/clip")


@pytest.mark.unit
def test_clip_factory_uses_builtin_transformers_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        scorer_mode="clip",
        scorer_weights_path=tmp_path / "unused.pth",
        scorer_weights_url="https://example.invalid/unused.pth",
        scorer_clip_model_name="test/clip-model",
        scorer_batch_size=4,
        scorer_device="cpu",
    )
    model_calls, processor_calls = _install_fake_transformers(monkeypatch)

    scorer = create_scorer(settings)
    dark_image = np.zeros((32, 32, 3), dtype=np.uint8)
    bright_image = np.full((32, 32, 3), 255, dtype=np.uint8)

    assert isinstance(scorer, CLIPScorer)
    scores = scorer.score_batch([dark_image, bright_image])
    assert scores[0] < 2.0
    assert scores[1] > 9.9
    assert model_calls == ["test/clip-model"]
    assert processor_calls == ["test/clip-model"]


@pytest.mark.unit
def test_create_scorer_uses_environment_settings_for_clip_mode(
    monkeypatch: pytest.MonkeyPatch,
    synthetic_scoring_references,
) -> None:
    captured: dict[str, object] = {}

    def fake_loader(*, model_name: str, batch_size: int) -> _FakeClipBackend:
        captured["model_name"] = model_name
        captured["batch_size"] = batch_size
        return _FakeClipBackend()

    monkeypatch.setattr("photos_pipeline.modules.scoring.backend.load_clip_backend", fake_loader)
    monkeypatch.setenv("PHOTOS_PIPELINE_SCORER_MODE", "clip")
    monkeypatch.setenv("PHOTOS_PIPELINE_SCORER_CLIP_MODEL_NAME", "env/clip-model")
    monkeypatch.setenv("PHOTOS_PIPELINE_SCORER_BATCH_SIZE", "5")
    monkeypatch.setenv("PHOTOS_PIPELINE_SCORER_DEVICE", "cpu")
    get_settings.cache_clear()

    try:
        scorer = create_scorer()
        scores = scorer.score_batch([reference.image for reference in synthetic_scoring_references[:2]])
    finally:
        get_settings.cache_clear()

    assert isinstance(scorer, CLIPScorer)
    assert scorer.device.type == "cpu"
    assert captured == {"model_name": "env/clip-model", "batch_size": 5}
    assert scores == [1.0, 2.0]
