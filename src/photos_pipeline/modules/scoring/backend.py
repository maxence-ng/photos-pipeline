"""Scoring backend implementations and factory helpers."""

from __future__ import annotations

import math
import shutil
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol, cast

import numpy as np
import torch
from PIL import Image
from torch import Tensor, nn
from torch.nn import functional as F
from torchvision import transforms

from photos_pipeline.config import Settings, get_settings

__all__ = [
    "AestheticScorer",
    "CLIPScorer",
    "CLIPScorerLoadError",
    "CLIPScorerUnavailableError",
    "ClipBackend",
    "IMAGENET_MEAN",
    "IMAGENET_STD",
    "MODEL_INPUT_SIZE",
    "NIMAScorer",
    "ScorerWeightsDownloadError",
    "ScorerWeightsError",
    "ScorerWeightsLoadError",
    "build_nima_model",
    "create_scorer",
    "download_weights",
    "expected_scores_from_model_output",
    "load_nima_model",
    "resolve_device",
    "resolve_weights_path",
]

IMAGENET_MEAN: tuple[float, float, float] = (0.485, 0.456, 0.406)
IMAGENET_STD: tuple[float, float, float] = (0.229, 0.224, 0.225)
MODEL_RESIZE_SIZE = 256
MODEL_INPUT_SIZE = 224
EXPECTED_SCORE_BUCKETS = 10
WEIGHTS_DOWNLOAD_SUFFIX = ".download"
_HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"
CLIP_POSITIVE_PROMPTS: tuple[str, ...] = (
    "a beautiful photo",
    "a stunning professional photograph",
    "a visually pleasing image",
    "an excellent composition",
)
CLIP_NEGATIVE_PROMPTS: tuple[str, ...] = (
    "a bad photo",
    "an ugly amateur snapshot",
    "a blurry poorly composed image",
    "a low quality image",
)
CLIP_SCORE_SCALING_FACTOR = 5.0


class AestheticScorer(Protocol):
    """Stable scorer API shared by backend implementations."""

    def score(self, image: np.ndarray) -> float:
        """Return an aesthetic score in the range ``[1.0, 10.0]``."""

    def score_batch(self, images: list[np.ndarray]) -> list[float]:
        """Return aesthetic scores for a batch of RGB images."""


class ClipBackend(Protocol):
    """Minimal pluggable surface for CLIP-backed scorers."""

    def score_batch(self, images: list[np.ndarray], *, device: torch.device) -> list[float]:
        """Return aesthetic scores for *images*."""


class _ClipModel(Protocol):
    def eval(self) -> _ClipModel:
        """Put the model into inference mode."""

    def to(self, device: torch.device) -> _ClipModel:
        """Move the model onto *device*."""

    def get_image_features(self, *, pixel_values: Tensor) -> object:
        """Return image embeddings or an output object containing them."""

    def get_text_features(self, **inputs: Tensor) -> object:
        """Return text embeddings or an output object containing them."""


class _ClipProcessor(Protocol):
    def __call__(
        self,
        *,
        text: Sequence[str] | None = None,
        images: Sequence[Image.Image] | None = None,
        return_tensors: str,
        padding: bool = False,
        truncation: bool = False,
    ) -> Mapping[str, Tensor]:
        """Encode text prompts or PIL images into CLIP input tensors."""


class ScorerWeightsError(RuntimeError):
    """Base class for NIMA weight resolution failures."""


class ScorerWeightsDownloadError(ScorerWeightsError):
    """Raised when weight download fails."""


class ScorerWeightsLoadError(ScorerWeightsError):
    """Raised when downloaded or configured weights cannot be loaded."""


class CLIPScorerUnavailableError(RuntimeError):
    """Raised when the CLIP scorer dependency stack is unavailable."""


class CLIPScorerLoadError(RuntimeError):
    """Raised when CLIP model assets cannot be loaded."""


def resolve_device(device: str) -> torch.device:
    """Resolve a configured device string into a concrete torch device."""
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    try:
        return torch.device(device)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported scorer device: {device!r}") from exc


def download_weights(url: str, destination: Path) -> None:
    """Download weights from *url* to *destination*."""
    request = urllib.request.Request(url, headers={"User-Agent": "photos-pipeline"})

    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except (OSError, urllib.error.URLError) as exc:
        raise ScorerWeightsDownloadError(
            f"Failed to download scorer weights from {url!r} to {destination}."
        ) from exc


def resolve_weights_path(
    weights_path: Path,
    weights_url: str,
    *,
    downloader: Callable[[str, Path], None] = download_weights,
) -> Path:
    """Return a local weights path, downloading it first when necessary."""
    if weights_path.exists():
        return weights_path

    if not weights_url:
        raise ScorerWeightsDownloadError(
            f"Scorer weights were not found at {weights_path} and no download URL was configured."
        )

    weights_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = weights_path.with_suffix(f"{weights_path.suffix}{WEIGHTS_DOWNLOAD_SUFFIX}")

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        downloader(weights_url, temporary_path)
        temporary_path.replace(weights_path)
    except Exception as exc:
        if temporary_path.exists():
            temporary_path.unlink()
        if isinstance(exc, ScorerWeightsDownloadError):
            raise
        raise ScorerWeightsDownloadError(
            f"Failed to download scorer weights from {weights_url!r} to {weights_path}."
        ) from exc

    return weights_path


def _as_rgb_image(image: np.ndarray) -> Image.Image:
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Scoring expects an RGB image array with shape (H, W, 3).")

    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)

    return Image.fromarray(image, mode="RGB")


def _normalise_embeddings(embeddings: Tensor) -> Tensor:
    return F.normalize(embeddings, dim=-1)


def _extract_clip_embeddings(output: object, *, output_kind: str) -> Tensor:
    if isinstance(output, Tensor):
        return output

    candidate_keys = ("image_embeds", "text_embeds", "pooler_output")

    if isinstance(output, Mapping):
        for key in candidate_keys:
            value = output.get(key)
            if isinstance(value, Tensor):
                return value

    for key in candidate_keys:
        value = getattr(output, key, None)
        if isinstance(value, Tensor):
            return value

    raise RuntimeError(
        f"CLIP {output_kind} feature extraction did not return a tensor embedding. "
        f"Received {type(output).__name__} instead."
    )


def _clip_probabilities_to_scores(probabilities: Tensor) -> list[float]:
    scores = probabilities.flatten().mul(9.0).add(1.0).clamp(1.0, 10.0)
    return [float(value) for value in scores.cpu()]


class _ImageNetPreprocessor:
    """Resize/crop RGB arrays into ImageNet-normalised tensors."""

    def __init__(self) -> None:
        self._transform = transforms.Compose(
            [
                transforms.Resize(MODEL_RESIZE_SIZE),
                transforms.CenterCrop(MODEL_INPUT_SIZE),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

    def preprocess_batch(self, images: Sequence[np.ndarray]) -> Tensor:
        tensors = [self._transform(_as_rgb_image(image)) for image in images]
        return torch.stack(tensors, dim=0)


def expected_scores_from_model_output(model_output: Tensor) -> list[float]:
    """Convert 10-way logits or probabilities into mean aesthetic scores."""
    if model_output.ndim == 1:
        model_output = model_output.unsqueeze(0)

    if model_output.ndim != 2 or model_output.shape[1] != EXPECTED_SCORE_BUCKETS:
        raise ValueError(
            "NIMA model output must have shape (batch, 10) to compute expected scores."
        )

    scores = model_output.detach()
    if not _looks_like_probabilities(scores):
        scores = torch.softmax(scores, dim=1)

    weights = torch.arange(1, EXPECTED_SCORE_BUCKETS + 1, device=scores.device, dtype=scores.dtype)
    expected = (scores * weights).sum(dim=1)
    return [float(value) for value in expected.cpu()]


def _looks_like_probabilities(values: Tensor) -> bool:
    return bool(
        torch.all(values >= 0)
        and torch.all(values <= 1)
        and torch.allclose(
            values.sum(dim=1),
            torch.ones(values.shape[0], device=values.device, dtype=values.dtype),
            atol=1e-4,
            rtol=1e-4,
        )
    )


def _conv_bn(in_channels: int, out_channels: int, stride: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True),
    )


def _conv_1x1_bn(in_channels: int, out_channels: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=1, padding=0, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True),
    )


class _InvertedResidual(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, stride: int, expand_ratio: int) -> None:
        super().__init__()
        if stride not in (1, 2):
            raise ValueError("MobileNetV2 inverted residual stride must be 1 or 2.")

        hidden_channels = in_channels * expand_ratio
        self.use_residual = stride == 1 and in_channels == out_channels
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, kernel_size=1, stride=1, padding=0, bias=False),
            nn.BatchNorm2d(hidden_channels),
            nn.ReLU6(inplace=True),
            nn.Conv2d(
                hidden_channels,
                hidden_channels,
                kernel_size=3,
                stride=stride,
                padding=1,
                groups=hidden_channels,
                bias=False,
            ),
            nn.BatchNorm2d(hidden_channels),
            nn.ReLU6(inplace=True),
            nn.Conv2d(hidden_channels, out_channels, kernel_size=1, stride=1, padding=0, bias=False),
            nn.BatchNorm2d(out_channels),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        outputs = cast(Tensor, self.conv(inputs))
        if self.use_residual:
            return cast(Tensor, inputs + outputs)
        return outputs


class _MobileNetV2(nn.Module):
    def __init__(self, *, input_size: int = MODEL_INPUT_SIZE, width_mult: float = 1.0) -> None:
        super().__init__()
        if input_size % 32 != 0:
            raise ValueError("MobileNetV2 input size must be divisible by 32.")

        block_settings: tuple[tuple[int, int, int, int], ...] = (
            (1, 16, 1, 1),
            (6, 24, 2, 2),
            (6, 32, 3, 2),
            (6, 64, 4, 2),
            (6, 96, 3, 1),
            (6, 160, 3, 2),
            (6, 320, 1, 1),
        )

        input_channel = int(32 * width_mult)
        last_channel = int(1280 * width_mult) if width_mult > 1.0 else 1280
        features: list[nn.Module] = [_conv_bn(3, input_channel, stride=2)]

        for expand_ratio, channels, repeats, stride in block_settings:
            output_channel = int(channels * width_mult)
            for repeat_index in range(repeats):
                block_stride = stride if repeat_index == 0 else 1
                features.append(
                    _InvertedResidual(input_channel, output_channel, block_stride, expand_ratio)
                )
                input_channel = output_channel

        features.append(_conv_1x1_bn(input_channel, last_channel))
        features.append(nn.AvgPool2d(input_size // 32))

        self.features = nn.Sequential(*features)
        self.classifier = nn.Sequential(nn.Dropout(), nn.Linear(last_channel, 1000))

        self._initialise_weights()

    def forward(self, inputs: Tensor) -> Tensor:
        outputs = cast(Tensor, self.features(inputs))
        outputs = outputs.view(outputs.size(0), -1)
        return cast(Tensor, self.classifier(outputs))

    def _initialise_weights(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                fan_out = module.kernel_size[0] * module.kernel_size[1] * module.out_channels
                module.weight.data.normal_(0, math.sqrt(2.0 / fan_out))
                if module.bias is not None:
                    module.bias.data.zero_()
            elif isinstance(module, nn.BatchNorm2d):
                module.weight.data.fill_(1)
                module.bias.data.zero_()
            elif isinstance(module, nn.Linear):
                module.weight.data.normal_(0, 0.01)
                module.bias.data.zero_()


class _NIMAModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        base_model = _MobileNetV2()
        self.base_model = nn.Sequential(*list(base_model.children())[:-1])
        self.head = nn.Sequential(
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.75),
            nn.Linear(1280, EXPECTED_SCORE_BUCKETS),
            nn.Softmax(dim=1),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        outputs = cast(Tensor, self.base_model(inputs))
        outputs = outputs.view(outputs.size(0), -1)
        return cast(Tensor, self.head(outputs))


def build_nima_model() -> nn.Module:
    """Build the default NIMA inference model."""
    return _NIMAModel()


def load_nima_model(weights_path: Path, device: torch.device) -> nn.Module:
    """Load NIMA weights into an inference model on *device*."""
    checkpoint_format = _detect_checkpoint_format(weights_path)
    if checkpoint_format == "hdf5":
        raise ScorerWeightsLoadError(
            f"Unsupported checkpoint format at {weights_path}: expected a PyTorch checkpoint, "
            "but found an HDF5/Keras weight file."
        )

    model = build_nima_model()
    try:
        checkpoint = torch.load(weights_path, map_location=device)
    except Exception as exc:
        raise ScorerWeightsLoadError(f"Failed to load scorer weights from {weights_path}.") from exc

    state_dict = _extract_state_dict(checkpoint)
    try:
        model.load_state_dict(state_dict)
    except RuntimeError as exc:
        raise ScorerWeightsLoadError(
            f"Failed to load scorer weights from {weights_path}: checkpoint contents did not match "
            "the NIMA model architecture."
        ) from exc

    model.to(device)
    model.eval()
    return model


def _detect_checkpoint_format(weights_path: Path) -> str:
    with weights_path.open("rb") as handle:
        signature = handle.read(len(_HDF5_SIGNATURE))
    if signature == _HDF5_SIGNATURE:
        return "hdf5"
    return "torch"


def _extract_state_dict(checkpoint: object) -> Mapping[str, Tensor]:
    if isinstance(checkpoint, Mapping):
        state_dict = checkpoint.get("state_dict") or checkpoint.get("model_state_dict")
        if state_dict is None:
            state_dict = checkpoint
    else:
        raise ScorerWeightsLoadError("Scorer checkpoint must be a torch state_dict or checkpoint map.")

    if not isinstance(state_dict, Mapping):
        raise ScorerWeightsLoadError("Scorer checkpoint did not contain a valid state_dict mapping.")

    return {
        str(key.removeprefix("module.")): value
        for key, value in state_dict.items()
        if isinstance(value, Tensor)
    }


class NIMAScorer:
    """NIMA-style aesthetic scorer with shared preprocessing and batched inference."""

    def __init__(
        self,
        *,
        weights_path: Path | None = None,
        weights_url: str | None = None,
        batch_size: int | None = None,
        device: str | None = None,
    ) -> None:
        settings = get_settings()
        configured_weights_path = weights_path or settings.scorer_weights_path
        configured_weights_url = weights_url or settings.scorer_weights_url
        configured_batch_size = batch_size or settings.scorer_batch_size
        configured_device = device or settings.scorer_device

        if configured_batch_size < 1:
            raise ValueError("Scorer batch size must be at least 1.")

        self.batch_size = configured_batch_size
        self.device = resolve_device(configured_device)
        self.weights_path = resolve_weights_path(configured_weights_path, configured_weights_url)
        self._preprocessor = _ImageNetPreprocessor()
        self._model = load_nima_model(self.weights_path, self.device)

    def score(self, image: np.ndarray) -> float:
        return self.score_batch([image])[0]

    def score_batch(self, images: list[np.ndarray]) -> list[float]:
        if not images:
            return []

        scores: list[float] = []
        for start_index in range(0, len(images), self.batch_size):
            batch_images = images[start_index : start_index + self.batch_size]
            batch_tensor = self._preprocessor.preprocess_batch(batch_images).to(self.device)
            with torch.inference_mode():
                model_output = self._model(batch_tensor)
            scores.extend(expected_scores_from_model_output(model_output))
        return scores


class _TransformersClipBackend:
    """Zero-shot CLIP backend backed by Hugging Face transformers."""

    def __init__(
        self,
        *,
        model_name: str,
        model: _ClipModel,
        processor: _ClipProcessor,
        batch_size: int,
        positive_prompts: Sequence[str] = CLIP_POSITIVE_PROMPTS,
        negative_prompts: Sequence[str] = CLIP_NEGATIVE_PROMPTS,
    ) -> None:
        if batch_size < 1:
            raise ValueError("Scorer batch size must be at least 1.")
        if not positive_prompts or not negative_prompts:
            raise ValueError("CLIP scoring requires at least one positive and one negative prompt.")

        self.model_name = model_name
        self.batch_size = batch_size
        self._model = model.eval()
        self._processor = processor
        self._positive_prompts = tuple(positive_prompts)
        self._negative_prompts = tuple(negative_prompts)
        self._active_device: str | None = None
        self._cached_prompt_device: str | None = None
        self._positive_prompt_embedding: Tensor | None = None
        self._negative_prompt_embedding: Tensor | None = None

    def score_batch(self, images: list[np.ndarray], *, device: torch.device) -> list[float]:
        if not images:
            return []

        self._ensure_model_device(device)
        positive_prompt_embedding, negative_prompt_embedding = self._get_prompt_embeddings(device)
        scores: list[float] = []

        for start_index in range(0, len(images), self.batch_size):
            batch_images = [_as_rgb_image(image) for image in images[start_index : start_index + self.batch_size]]
            image_inputs = self._processor(images=batch_images, return_tensors="pt")
            pixel_values = image_inputs["pixel_values"].to(device)

            with torch.inference_mode():
                image_features = _extract_clip_embeddings(
                    self._model.get_image_features(pixel_values=pixel_values),
                    output_kind="image",
                )

            image_features = _normalise_embeddings(image_features)
            positive_similarity = cast(Tensor, image_features @ positive_prompt_embedding)
            negative_similarity = cast(Tensor, image_features @ negative_prompt_embedding)
            positive_probability = torch.sigmoid(
                (positive_similarity - negative_similarity) * CLIP_SCORE_SCALING_FACTOR
            )
            scores.extend(_clip_probabilities_to_scores(positive_probability))

        return scores

    def _ensure_model_device(self, device: torch.device) -> None:
        device_key = str(device)
        if self._active_device == device_key:
            return

        self._model.to(device)
        self._active_device = device_key
        self._cached_prompt_device = None

    def _get_prompt_embeddings(self, device: torch.device) -> tuple[Tensor, Tensor]:
        device_key = str(device)
        if (
            self._cached_prompt_device == device_key
            and self._positive_prompt_embedding is not None
            and self._negative_prompt_embedding is not None
        ):
            return self._positive_prompt_embedding, self._negative_prompt_embedding

        self._positive_prompt_embedding = self._encode_prompt_group(self._positive_prompts, device)
        self._negative_prompt_embedding = self._encode_prompt_group(self._negative_prompts, device)
        self._cached_prompt_device = device_key
        return self._positive_prompt_embedding, self._negative_prompt_embedding

    def _encode_prompt_group(self, prompts: Sequence[str], device: torch.device) -> Tensor:
        text_inputs = self._processor(
            text=list(prompts),
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        text_inputs = {key: value.to(device) for key, value in text_inputs.items()}

        with torch.inference_mode():
            text_features = _extract_clip_embeddings(
                self._model.get_text_features(**text_inputs),
                output_kind="text",
            )

        centroid = _normalise_embeddings(text_features).mean(dim=0, keepdim=True)
        return _normalise_embeddings(centroid).squeeze(0)


def load_clip_backend(*, model_name: str, batch_size: int) -> ClipBackend:
    """Build the default CLIP zero-shot backend."""
    try:
        from transformers import CLIPModel, CLIPProcessor
    except ImportError as exc:
        raise CLIPScorerUnavailableError(
            "CLIP scorer mode requires the optional 'transformers' dependency."
        ) from exc

    try:
        model = cast(_ClipModel, CLIPModel.from_pretrained(model_name))
        processor = cast(_ClipProcessor, CLIPProcessor.from_pretrained(model_name))
    except Exception as exc:
        raise CLIPScorerLoadError(
            f"Failed to load CLIP scorer model {model_name!r}. Ensure the model name is valid and "
            "that the model can be downloaded or is already cached."
        ) from exc

    return _TransformersClipBackend(
        model_name=model_name,
        model=model,
        processor=processor,
        batch_size=batch_size,
    )


class CLIPScorer:
    """CLIP zero-shot aesthetic scorer with optional backend injection."""

    def __init__(
        self,
        *,
        backend: ClipBackend | None = None,
        device: str = "auto",
        batch_size: int | None = None,
        model_name: str | None = None,
    ) -> None:
        settings = get_settings()
        configured_batch_size = batch_size if batch_size is not None else settings.scorer_batch_size
        configured_model_name = (
            model_name if model_name is not None else settings.scorer_clip_model_name
        )

        if configured_batch_size < 1:
            raise ValueError("Scorer batch size must be at least 1.")

        self.device = resolve_device(device)
        self._backend = backend or load_clip_backend(
            model_name=configured_model_name,
            batch_size=configured_batch_size,
        )

    def score(self, image: np.ndarray) -> float:
        return self.score_batch([image])[0]

    def score_batch(self, images: list[np.ndarray]) -> list[float]:
        return self._backend.score_batch(images, device=self.device)


def create_scorer(
    settings: Settings | None = None,
    *,
    clip_backend: ClipBackend | None = None,
) -> AestheticScorer:
    """Create the configured scorer backend."""
    active_settings = settings or get_settings()

    if active_settings.scorer_mode == "nima":
        return NIMAScorer(
            weights_path=active_settings.scorer_weights_path,
            weights_url=active_settings.scorer_weights_url,
            batch_size=active_settings.scorer_batch_size,
            device=active_settings.scorer_device,
        )

    if active_settings.scorer_mode == "clip":
        return CLIPScorer(
            backend=clip_backend,
            device=active_settings.scorer_device,
            batch_size=active_settings.scorer_batch_size,
            model_name=active_settings.scorer_clip_model_name,
        )

    raise ValueError(f"Unsupported scorer mode: {active_settings.scorer_mode!r}")
