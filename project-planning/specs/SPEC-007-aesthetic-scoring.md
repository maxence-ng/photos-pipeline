---
id: SPEC-007
title: "Aesthetic Scoring (NIMA)"
status: todo
phase: mvp
epic: scoring
priority: high
effort: L
depends_on: ["SPEC-002"]
---

## User Story
As a user, I want each photo ranked by an AI aesthetic score (1–10) so that the pipeline can prioritise the most visually compelling images when culling or selecting from bursts.

## Acceptance Criteria
- [ ] `AestheticScorer.score(image: np.ndarray) -> float` returns a score in [1.0, 10.0]
- [ ] `AestheticScorer.score_batch(images) -> list[float]` processes a list efficiently (batched inference)
- [ ] Scores are stored in `ImageRecord.aesthetic_score`
- [ ] Model loads from `~/.photos_pipeline/models/nima_weights.pth`; if absent, download from a documented URL (or prompt user)
- [ ] GPU used automatically when available (`torch.cuda.is_available()`); falls back to CPU
- [ ] Batch inference time: < 1 s/image on CPU for 224×224 input
- [ ] CLIP zero-shot mode available as a fallback (`--scorer clip`) requiring no extra download
- [ ] Unit tests: pre-scored reference images — expected output within ±0.5 of known score

## Technical Notes
- NIMA architecture: MobileNetV2 backbone with a 10-class softmax head; score = `sum(i * p_i for i in 1..10)`
- Pre-trained weights: use public NIMA checkpoint trained on AVA dataset (MIT license)
- Input normalisation: ImageNet mean/std, resize to 224×224
- CLIP fallback: compare image embedding against prompts like `"a beautiful photo"` vs `"a bad photo"` and derive a score from cosine similarity

## Implementation Hints
```python
import torch
from torchvision import transforms, models

class NIMAScorer:
    def __init__(self, weights_path: Path, device: str = "auto"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") \
                      if device == "auto" else torch.device(device)
        self.model = self._load_model(weights_path)
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

    def score(self, image: np.ndarray) -> float:
        tensor = self.transform(Image.fromarray(image)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(tensor), dim=1).squeeze()
        weights = torch.arange(1, 11, dtype=torch.float, device=self.device)
        return float((probs * weights).sum())
```
