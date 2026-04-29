# Résumé exécutif

Ce projet vise à développer un pipeline automatique de post-traitement photo (70–80 % des retouches) utilisant des outils open-source et de l’IA. Le système prendra en entrée un lot d’images RAW/JPEG et appliquera : (1) un tri automatique (« culling ») pour supprimer les photos floues, en double ou aux yeux fermés, (2) la sélection de la meilleure photo en cas de rafale, (3) des corrections globales (exposition, balance des blancs, recadrage intelligent) et l’application de presets personnalisés, (4) l’export multi-format (Web, client, print) avec conservation des métadonnées. L’architecture s’appuiera sur Python, OpenCV et PyTorch, ainsi que sur des outils dédiés comme Darktable (mode CLI) pour les retouches fines et ExifTool pour la gestion des métadonnées. Un modèle d’évaluation esthétique entraîné (sur AVA ou un dataset dédié) classera les images selon leur qualité perçue. L’interface comprendra une CLI et une UI Web, accompagnées de schémas d’architecture (Mermaid) et de tables comparatives pour éclairer les choix techniques. Un plan de tests (unitaires, intégration, dataset de test), un pipeline CI/CD GitHub Actions, et une roadmap détaillée (MVP, backlog, estimation, risques) complètent ce PRD exhaustif. Enfin, des questions ouvertes sont listées pour clarifier les préférences de style, les contraintes opérationnelles et les exigences du projet. 

【33†embed_image】 *Exemple d’interface de retouche (évoquant l’UI du pipeline). En entrée, l’utilisateur soumet un dossier de photos, et le système automatique applyera corrections et presets avant export.* 

## 1. Objectifs

- **Automatisation élevée (70–80 %)** du post-traitement photo, pour réduire l’effort manuel.  
- **Auto-culling** : détecter et filtrer les images indésirables  
  - **Flou** : évaluer la netteté (variance de Laplacien)【42†L189-L198】, seuiler pour supprimer les images floues.  
  - **Doublons/quasi-doublons** : détection par hachage perceptuel (pHash/DHash/AHash) ou CNN【15†L71-L80】 pour ne conserver qu’une occurrence.  
  - **Yeux fermés** : détection de visages et landmarks (OpenCV) pour éliminer les portraits où les sujets ont les yeux fermés.  
- **Meilleure photo en rafale** : identifier dans une rafale la prise de vue optimale, par tri selon la netteté et l’esthétique (score IA).  
- **Corrections automatiques** : appliquer des réglages globaux sur chaque image survivante.  
  - **Exposition & Balance des blancs** : ajustements automatiques (OpenCV ou Darktable).  
  - **Recadrage intelligent** : recentrer l’image sur le sujet principal (par détection de visage/sujet)【18†L49-L53】【18†L60-L64】 ou composition (règle des tiers).  
  - **Presets personnalisés** : appliquer un style global (Darktable *style* ou presets) choisi par l’utilisateur pour obtenir une ambiance cohérente. Darktable CLI supporte l’option `--style` pour appliquer un style enregistré【4†L75-L84】.  
- **Export multi-format** : générer des variantes optimisées pour le Web (JPEG compressé), client (TIFF/PNG haute qualité), print (TIFF ou PDF) avec métadonnées. Par exemple, JPEG (qualité 5–100【46†L7-L9】) pour le Web, TIFF non-compressé pour l’archivage professionnel, éventuellement JPEG2000/JXL pour l’impression de haute qualité.  
- **Compatibilité RAW et JPEG** : prise en charge des formats RAW courants (CR2, NEF, RAF, etc.) et des JPEG. L’export doit aussi préserver/écrire les métadonnées (EXIF/IPTC/XMP) via ExifTool【23†L65-L69】.  
- **Intégrité des métadonnées** : ExifTool garantira la lecture/écriture fiables des tags (EXIF GPS, modèles d’APN, copyrights)【23†L65-L69】.  

## 2. Périmètre fonctionnel détaillé

- **Ingestion** : import des images depuis un dossier ou un service (CLI ou upload Web). Gestion des fichiers en lot, support du paramètre `--import` de Darktable CLI【4†L29-L36】.  
- **Culling automatique** : pipeline qui identifie et supprime les images à problèmes.  
  - *Flou* : calcul de la variance du Laplacien sur l’image en niveaux de gris【42†L189-L198】. Si la variance est en dessous d’un seuil paramétrable, l’image est marquée floue.  
  - *Doublons* : calcul d’une empreinte visuelle (pHash) pour chaque image. Le module “imagededup” offre des fonctions de hachage perceptuel pour détecter doublons【15†L71-L80】. Les images similaires (pHash proches) sont notifiées pour révision/suppression.  
  - *Yeux fermés* : détection de visages (OpenCV Cascade ou DNN) et analyse de landmarks (yeux). Les portraits avec yeux fermés sont isolés.  
  - *Filtrage utilisateur* : possibilité de configurer finement (seuils, critères) pour le culling.  
- **Sélection des meilleures photos** :  
  - *Rafales* : regrouper les photos proches (horodatage) et choisir la plus nette (score de focus) ou la mieux notée par l’algorithme esthétique.  
  - *Tri final* : classement des images par score d’esthétique (voir section scoring). Permettre à l’utilisateur de revoir les top-n si besoin.  
- **Traitements automatiques** : pour chaque image retenue :  
  - Ajustement *exposition* et *balance des blancs* automatique (Darktable offre des outils avancés pour cela).  
  - Application d’un *recadrage automatique* centré sur le sujet principal (via détection de visages ou objets) pour respecter une composition optimale【18†L49-L53】【18†L60-L64】.  
  - Application de *presets/styles* : Darktable CLI permet d’appliquer un style prédéfini (--style) ou un set de presets personnalisés【4†L75-L84】. Les utilisateurs pourront définir des styles pour différents usages (portrait, paysage, etc.).  
- **Export multi-format** :  
  - Web : JPEG compressé à la qualité souhaitée (ex. 80)【46†L7-L9】.  
  - Usage client : TIFF 16 bits ou PNG pour édition ultérieure.  
  - Impression : TIFF 16 bits ou PDF avec résolution adaptée.  
  - Ajout de filigrane/logo si requis (non couvert par Darktable nativement, peut être fait par PIL/OpenCV après export).  
  - Écriture ou mise à jour des métadonnées (Exif/IPTC) via ExifTool【23†L65-L69】 au moment de l’export.  
- **Interface utilisateur (UX/UI)** :  
  - *CLI* : un outil en ligne de commande (Python) pour traiter en batch (`photos-pipeline process --input A --output B --style C`).  
  - *Web UI* (optionnel) : un front-end simple (React/Flask) permettant d’uploader des images, surveiller le pipeline, visualiser les résultats et télécharger les exports. Les flows prévus : import → présélection (ajuster seuils de culling) → visualiser/valider top photos → lancer export.  

## 3. Exigences non-fonctionnelles

- **Performance** : traiter efficacement de grands volumes (p. ex. centaines d’images) en parallélisant les étapes (multi-thread ou GPU pour le scoring).  
- **Latence** : pour usage semi-temps réel (p. ex. studio photo), viser un temps de traitement moyen faible (< quelques secondes par image).  
- **Scalabilité** : l’architecture doit être extensible (exécution locale multi-cœurs ou déploiement conteneurisé sur cloud). Par ex., version Docker/Kubernetes, ou service serverless pour la commande CLI.  
- **Sécurité** : s’assurer que les images (potentiellement sensibles) ne sont pas exposées publiquement. Les transferts HTTPS et stockage crypté (si cloud) sont recommandés. Gestion des permissions (projets privés).  
- **Compatibilité multiplateforme** : fonctionner sur Linux/Mac/Windows.  
- **Fiabilité** : prévoir journaux détaillés, reprise après erreur, tests unitaires et d’intégration.  
- **Conformité des métadonnées** : tous les formats supportés (JPEG, TIFF, RAW) doivent lire/écrire EXIF/XMP correctement【23†L65-L69】.  
- **Licence** : prévoir une licence open-source (MIT/Apache/GPL selon préférence).  
- **Interopérabilité** : facile à intégrer dans d’autres workflows (bibliothèques Python, API REST).  

## 4. Architecture technique

L’architecture est modulaire, comme illustré schématiquement ci-dessous. 

【36†embed_image】 *Schéma conceptuel du pipeline automatique de retouche photo (ci-dessus, exemple de diagramme de flux). Chaque module (culling, scoring, correction, export) s’enchaîne de façon autonome mais est coordonné par le contrôleur principal.* 

- **Stack logicielle principale** : Python 3 + bibliothèques (OpenCV, NumPy/PIL pour la manipulation d’image), PyTorch pour le scoring esthétique, Darktable CLI pour le traitement RAW, ExifTool CLI pour métadonnées.  
- **Darktable CLI** : utilisé en mode sans GUI pour appliquer styles/presets et exporter les images【4†L20-L25】. Par exemple :  
  ```
  darktable-cli input.cr2 --style "MonStyle" output.jpg
  ```  
  Darktable CLI fonctionne en batch sans interface graphique (utile en serveur)【4†L20-L25】. L’option `--apply-custom-presets` active les presets personnalisés, et `--style` applique un style existant【4†L75-L84】.  
- **Module de culling** : script Python avec OpenCV/PIL. Exemples de tâches : flou (variance de Laplacien)【42†L189-L198】, doublons (pHash via [15]), yeux fermés (OpenCV Haar).  
- **Module de scoring esthétique** : un réseau CNN entraîné (PyTorch) sur le dataset AVA【11†L462-L468】, ou un modèle pré-entraîné (NIMA)【11†L505-L510】. Les images sont normalisées et passées dans le modèle qui produit une note continue (moyenne de notation humaine)【11†L462-L468】. Le modèle peut être affiné via un retour utilisateur (feedback de sélection d’images).  
- **API / CLI** : le **CLI** principal (`photos-pipeline`) orchestre le processus (import, appel modules, export). L’**API REST** (Flask/FastAPI) expose des endpoints : par ex. `POST /process` (démarrer pipeline sur un dossier), `GET /status`, `GET /results`. Les endpoints acceptent des paramètres JSON (formats d’export, style, seuils).  
- **UI Web** : front-end léger (React/Vue) communiquant avec l’API. Permet l’upload, visualisation du statut, pré-sélection des images retenues et déclenchement du pipeline.  
- **Stockage** : système de fichiers local ou bucket cloud pour les images intermédiaires et résultats.  
- **CI/CD** : pipelines GitHub Actions【45†L269-L274】 pour automatiser les tests (pytest) et le déploiement (packaging du CLI).  

## 5. Scoring esthétique personnalisé

- **Jeu de données** : base initiale AVA (≈255 522 images avec notes 1–10)【11†L462-L468】. Possibilité de composer un dataset métier (ex. photos de paysages spécifiques), avec annotations par un photographe expert.  
- **Méthode d’entraînement** : utiliser PyTorch pour fine-tuner un modèle (par exemple ResNet ou Vision Transformer) sur AVA. NIMA est une approche courante (remplacer la tête de classification par une distribution de notes, apprentissage avec perte EMD)【11†L505-L510】. On peut aussi explorer les prompts CLIP (pas d’entraînement, mais bonne performance zéro-shot)【11†L505-L510】.  
- **Labels** : score moyen de l’AVA comme « ground truth » pour l’esthétique【11†L462-L468】. On peut aussi prévoir un mode de feedback : après chaque session, l’utilisateur note les meilleurs clichés, affinant le modèle (apprentissage continu).  
- **Métriques** : pour évaluer, on utilisera la corrélation de Pearson et de Spearman entre notes prédictes et vraies (mesure la précision linéaire et le classement)【11†L476-L482】. Un bon modèle IAA (Image Aesthetic Assessment) dépassera ~0.6 sur Spearman【10†L25-L33】.  
- **Validation** : séparer training/validation sur AVA. Suivre MAE/MSE, EMD loss pendant l’entraînement. Tester aussi sur un petit jeu de test interne.  

## 6. UX/UI Flows

- **Flux d’utilisation CLI** :  
  1. `photos-pipeline ingest --input /images/raw/ --output /images/processed/ --preset ProPreset` : importe et traite en une fois.  
  2. Affichage console de progression, rapport de culling (ex. « 12 doublons supprimés, 3 flou supprimées »).  
- **Flux d’utilisation Web UI** :  
  1. Page d’accueil : bouton *Nouvelle session*.  
  2. Upload/Sélection d’un dossier d’images (drag & drop).  
  3. Réglage des paramètres : seuil de flou, filtres, choix de style Darktable.  
  4. Prévisualisation : liste des images retenues après culling (miniatures) avec notes et possibilité de décocher.  
  5. Lancement du pipeline (bouton *Traiter*). Barre de progression.  
  6. Affichage des résultats : galerie des exports finaux par format, liens de téléchargement.  
  7. Module de feedback (étoiles pour noter les images finales) pour ajuster le modèle esthétique.  

## 7. API et CLI Specifications

- **API REST (exemples)** :  
  - `POST /api/start` – JSON `{ "input_dir": "...", "output_dir": "...", "style": "...", "threshold_blur": 100 }` retourne un ID de job.  
  - `GET /api/status/{job_id}` – statut (en cours, terminé, erreurs).  
  - `GET /api/results/{job_id}` – liens vers images exportées.  
  - Authentication/token pour usages privés.  
- **CLI** :  
  ```
  photos-pipeline process \
    --input /chemin/RAW/ --output /chemin/Out/ \
    --cull --style "PortraitWarm" \
    --export jpg png tiff \
    --quality-web 85 --quality-print 100
  ```  
  Flags principaux : `--input`, `--output`, `--style`, `--cull`, `--export` (formats), `--threads`, etc. Le CLI s’appuie sur darktable-cli et exiftool en arrière-plan.  

## 8. Schémas d’architecture (Mermaid)

```mermaid
flowchart LR
    A[📥 Import Images] --> B[Culling]
    B --> C[Scoring esthétique]
    C --> D[Corrections (Darktable)]
    D --> E[Export & Métadonnées]
    E --> F[🏁 Résultat final]
```

*(Chaque étape ci-dessus représente un composant. Le workflow est piloté par un orchestrateur Python.)*  

## 9. Tableaux comparatifs

| Fonctionnalité             | Option 1                              | Option 2                           | Remarques                                       |
|----------------------------|---------------------------------------|------------------------------------|-------------------------------------------------|
| **Détection de flou**      | Variance du Laplacien (OpenCV)【42†L189-L198】 | CNN spécialisé (type NIMA)         | Laplacien : simple et rapide, mais sensible au bruit【42†L189-L198】. CNN : plus précis mais nécessite un entraînement. |
| **Détection de doublons**  | Hachage perceptuel (pHash)【15†L71-L80】      | Réseau de similarité (CNN)        | pHash : très rapide pour doublons exacts. CNN (imagededup) : meilleur pour transformations d’images【15†L71-L80】. |
| **Recadrage intelligent**  | Détection de visages (OpenCV)【18†L62-L64】   | Smart-crop (Azure API)【18†L49-L53】 | Visages : couvre cas portrait. SmartCrop : détecte visage + composition (libre service payant)【18†L49-L53】【18†L62-L64】.     |
| **Style/Presets**          | Darktable CLI (`--style`)【4†L75-L84】       | Script Python custom (OpenCV)     | Darktable : qualité photo élevée et styles flexibles【4†L75-L84】. OpenCV : plus basique, moins précis en RAW.          |
| **Scoring esthétique**     | NIMA (CNN, EMD loss)【11†L505-L510】         | CLIP + prompts【11†L476-L482】      | NIMA : entrainé sur AVA, perf. éprouvée【11†L505-L510】. CLIP : méthode zéro-shot prometteuse (pas de formation)【11†L476-L482】. |

| Format Export | Usage                   | Qualité (optim.)           | Remarques                                                              |
|---------------|-------------------------|----------------------------|------------------------------------------------------------------------|
| **JPEG (.jpg)** | Web / Clients légers   | 70–90 (binaire)【46†L7-L9】 | Diffusion web; compression avec perte (qualité 5–100【46†L7-L9】). Paramètre `quality` géré par Darktable. |
| **PNG**       | Graphiques, Web         | Sans perte (aucun paramètre) | Idéal pour images sans perte (logos). Taille > JPEG.                   |
| **TIFF**      | Impression, Archivage   | Sans perte (16 bits)       | Qualité maximale, très volumineux. Exif et calques gérés.               |
| **PDF**       | Albums, Documentation   | Variable                  | Peut contenir plusieurs pages. Utilisé pour rapports/photo-livres.      |

## 10. Plan de tests

- **Tests unitaires** : valider chaque fonction de culling et d’export (PyTest). Ex : la fonction de variance de Laplacien retourne une valeur cohérente pour images floues/nettes.  
- **Tests d’intégration** : pipeline de bout en bout sur un petit jeu de données (ex. 50 images mixtes). Vérifier qu’aucune erreur et que les bons fichiers sont produits.  
- **Jeu de test** : inclure des images exemples (floues, avec doublons, portraits aux yeux fermés, paysages, etc.). Garder ces données en référence (similaires à AVA).  
- **Tests de performance** : mesurer le temps de traitement en batch. Évaluer l’utilisation CPU/GPU.  
- **CI (GitHub Actions)** : automatiser l’exécution des tests à chaque commit (unit, lint, analyse statique).  

## 11. Déploiement et CI/CD

- **GitHub Actions**【45†L269-L274】 : configurer un workflow pour installer l’environnement Python, exécuter les tests et déployer le CLI (packaging PyPI ou container Docker).  
- **Docker** : fournir une image Docker contenant toutes les dépendances (Darktable CLI préinstallé, ExifTool, librairies Python) pour faciliter le déploiement (CI/CD).  
- **Environnements** : par défaut pipeline local, mais possibilité de conteneur ou serveur (par ex. GitHub-hosted runner pour CI).  
- **Documentation automatisée** : génération de docs (mkdocs ou Sphinx) en CI et mise à jour sur GitHub Pages.  

## 12. Roadmap & Backlog MVP

1. **MVP** :  
   - Setup du dépôt GitHub avec CI.  
   - Implémentation du CLI de base (ingestion, culling flou et doublons).  
   - Intégration Darktable CLI pour correction de base et export JPEG.  
   - Prototype de scoring (import d’un modèle NIMA pré-entraîné) et tri.  
2. **Fonctionnalités intermédiaires** :  
   - Correction WB/Expo automatique.  
   - Détection yeux fermés.  
   - Export multi-format avancé (PNG/TIFF, watermark).  
   - Développement d’un dataset personnalisé et affinage du modèle esthétique.  
   - Déploiement de l’UI Web basique.  
3. **Améliorations avancées** :  
   - Module de feedback utilisateur (ré-entraînement du modèle).  
   - Scalaibilité (GPU, parallélisme).  
   - Support de presets Darktable plus complexes (masques, etc.).  
   - Tests approfondis et audit de performance.  

## 13. Estimation des efforts & Risques

- **Efforts** : environ 3–6 mois de développement pour une petite équipe (1 dev photo, 1 dev ML), selon disponibilité des datasets.  
- **Risques** :  
  - *Qualité de l’IA esthétique* : la subjectivité peut décevoir les utilisateurs. Mitigation : garder une option de réglage manuel.  
  - *Performance* : Darktable CLI est lourd ; traitement GPU partiel (PyTorch) ou multi-thread nécessaire.  
  - *Interopérabilité RAW* : bien tester sur différentes marques d’APN ; Darktable supporte la plupart via libraw.  
  - *Sécurité/Confidentialité* : si projet interne, prévoir chiffrement et accès restreint.  
  - *Maintenance* : dépendances de Darktable/PyTorch en évolution ; prévoir mises à jour régulières.  

## 14. Questions ouvertes

- **Préférences de style** : quelle ambiance (contraste fort, tons doux, B&W) privilégier ? Préfère-t-on colorimétrie naturelle ou traitement créatif ?  
- **Contraintes de performance** : quels volumes d’images simultanés et latence acceptable (temps maxi par image) ?  
- **Formats supportés** : faut-il gérer tous les RAW (CR2, NEF, RW2, ORF, ARW…)? Et quels formats JPEG (origine DSLR, smartphones) ?  
- **Workflow client** : qui utilisera cet outil (photographes pros, agences, amateurs) et comment ? Intégration à d’autres outils existants ?  
- **Budget et infra** : déploiement sur serveur dédié ou cloud (AWS, GCP) ? Budget matériel/GPU disponible ?  
- **Confidentialité des images** : nécessité de chiffrer les images au repos ? Politiques de suppression après traitement ?  
- **Licence du projet** : quelle licence open-source (MIT, Apache 2.0, GPL) ?  
- **Niveau d’automatisation** : validation manuelle aux étapes-clés (culling, sélection finale) ou tout automatique ?  
- **Exemples d’images** : fournir quelques photos représentatives (paysage, portrait, événement) pour calibrer l’algorithme esthétique et les presets.  

**Sources :** documentation officielle Darktable【4†L20-L25】【4†L75-L84】, ExifTool【23†L65-L69】, articles académiques sur l’évaluation esthétique【11†L462-L468】【11†L505-L510】, modules Python recommandés【15†L71-L80】【42†L189-L198】, et documentation GitHub Actions【45†L269-L274】. Chaque élément de ce PRD s’appuie sur ces références pour garantir des fondations solides et à jour.