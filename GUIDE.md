# 🎮 JobsRadar 3D — Guide de déploiement complet

**Bot de veille automatique** pour les offres de **stage & alternance** en France  
Domaines : 3D · OpenGL · Vulkan · Unreal Engine · Unity · VR/AR · Computer Graphics · Rendering · Shaders · VFX

---

## Architecture

```
Ton GitHub (repo public)
├── main.py              ← Backend FastAPI (scraping + IA)
├── requirements.txt     ← Dépendances Python
├── railway.json         ← Config déploiement Railway
├── nixpacks.toml        ← Config build Railway
├── Procfile             ← Commande de démarrage
├── runtime.txt          ← Version Python
└── frontend/
    └── index.html       ← Dashboard web (hébergé sur GitHub Pages)
```

**Backend → Railway** (serveur cloud gratuit, tourne 24h/24)  
**Frontend → GitHub Pages** (site statique gratuit, ton dashboard)

---

## Étape 1 — Installer Git

### Windows
1. Va sur https://git-scm.com/download/win
2. Télécharge et installe (laisse toutes les options par défaut)
3. Ouvre **Git Bash** (clic droit sur le bureau → "Git Bash Here")
4. Vérifie :
   ```bash
   git --version
   # Doit afficher : git version 2.x.x
   ```

---

## Étape 2 — Créer un compte GitHub

1. Va sur https://github.com
2. Clique **Sign up** (gratuit)
3. Confirme ton email

---

## Étape 3 — Créer le repo GitHub

1. Sur GitHub, clique **"+"** en haut à droite → **New repository**
2. Nom du repo : `jobsradar-3d`
3. Coche **Public**
4. **Ne coche pas** "Add README"
5. Clique **Create repository**
6. Garde cette page ouverte (tu en as besoin après)

---

## Étape 4 — Envoyer le code sur GitHub

Ouvre **Git Bash** et tape ces commandes une par une :

```bash
# 1. Déplace-toi sur le Bureau (ou là où tu as le dossier)
cd ~/Desktop

# 2. Clone/initialise le dossier jobsradar-3d
#    (remplace TON_USERNAME par ton nom d'utilisateur GitHub)
git clone https://github.com/TON_USERNAME/jobsradar-3d.git
cd jobsradar-3d
```

Maintenant **copie les fichiers** du ZIP que tu as téléchargé dans ce dossier `jobsradar-3d`.  
La structure doit ressembler à ceci :
```
jobsradar-3d/
├── main.py
├── requirements.txt
├── railway.json
├── nixpacks.toml
├── Procfile
├── runtime.txt
├── .gitignore
├── GUIDE.md
└── frontend/
    └── index.html
```

Puis envoie tout sur GitHub :
```bash
git add .
git commit -m "🚀 Initial deploy JobsRadar 3D"
git push origin main
```

> 💡 Si Git te demande ton identité :
> ```bash
> git config --global user.email "ton@email.com"
> git config --global user.name "Ton Nom"
> ```

---

## Étape 5 — Obtenir les clés API gratuites

### Groq (IA principale — GRATUIT)
1. Va sur https://console.groq.com
2. Clique **Sign Up** (gratuit, pas de carte bancaire)
3. Dans le menu gauche → **API Keys** → **Create API Key**
4. Copie la clé (commence par `gsk_...`)
5. Garde-la dans un bloc-notes

### Gemini (IA de secours — GRATUIT)
1. Va sur https://aistudio.google.com
2. Connecte-toi avec ton compte Google
3. Clique **Get API key** → **Create API key**
4. Copie la clé (commence par `AIza...`)
5. Garde-la dans un bloc-notes

> ℹ️ Ces deux IA sont **100% gratuites** pour notre usage (limits très généreuses)

---

## Étape 6 — Déployer le backend sur Railway

### 6.1 Créer un compte Railway
1. Va sur https://railway.app
2. Clique **Login** → **Login with GitHub**
3. Autorise Railway à accéder à ton GitHub

### 6.2 Créer le projet
1. Clique **New Project**
2. Clique **Deploy from GitHub repo**
3. Sélectionne `TON_USERNAME/jobsradar-3d`
4. Railway détecte automatiquement le backend Python ✓
5. Clique **Deploy Now**

> ✅ **Cette fois ça marche** parce que `main.py` et `requirements.txt` sont à la **racine** du repo.

### 6.3 Configurer les variables d'environnement
1. Clique sur ton service dans Railway (le cube violet)
2. Onglet **Variables**
3. Clique **New Variable** pour chaque ligne :

| Variable | Valeur |
|---|---|
| `GROQ_API_KEY` | Ta clé Groq (`gsk_...`) |
| `GEMINI_API_KEY` | Ta clé Gemini (`AIza...`) |
| `SCANS_PER_DAY` | `4` |

4. Clique **Save** — Railway redémarre automatiquement

### 6.4 Récupérer l'URL du backend
1. Onglet **Settings** → section **Networking** → **Generate Domain**
2. Clique **Generate Domain**
3. Tu obtiens une URL du type : `https://jobsradar-3d-production-XXXX.up.railway.app`
4. **Copie cette URL** — tu en as besoin pour le frontend

### 6.5 Vérifier que le backend tourne
Ouvre l'URL dans ton navigateur. Tu dois voir :
```json
{
  "status": "running",
  "jobs": 0,
  "scan_count": 0,
  "last_scan": null,
  "ai": {"groq": true, "gemini": true}
}
```
> Si `"groq": true` et `"gemini": true` → les clés API sont bien configurées ✓

---

## Étape 7 — Activer GitHub Pages (frontend)

1. Sur GitHub, va dans ton repo `jobsradar-3d`
2. Onglet **Settings** (en haut)
3. Menu gauche → **Pages**
4. Section **Source** → sélectionne **Deploy from a branch**
5. Branch : **main** / Folder : **/frontend** (ou `/root` si Pages propose `/docs`)

> ⚠️ Si GitHub Pages ne propose pas `/frontend`, utilise cette méthode alternative :

**Méthode alternative pour GitHub Pages :**
1. Copie `frontend/index.html` à la racine avec le nom `index.html`
2. Dans Git Bash :
   ```bash
   cp frontend/index.html index.html
   git add index.html
   git commit -m "Add root index.html for GitHub Pages"
   git push origin main
   ```
3. Dans Settings → Pages → Source : **main** / Folder : **/ (root)**

Après ~2 minutes, ton dashboard est accessible sur :
```
https://TON_USERNAME.github.io/jobsradar-3d/
```

---

## Étape 8 — Configurer le dashboard

1. Ouvre ton dashboard GitHub Pages
2. Dans la **bannière bleue** en haut, colle l'URL de ton backend Railway :
   ```
   https://jobsradar-3d-production-XXXX.up.railway.app
   ```
3. Clique **Connecter**
4. Le dashboard se connecte au backend ✓

---

## Étape 9 — Premier scan !

1. Dans le dashboard, clique le bouton **🔍 Scanner**
2. Le scan tourne en arrière-plan (~30-60 secondes)
3. Les offres apparaissent automatiquement
4. Le compteur "Prochain scan" s'affiche

> ✅ Le backend relance automatiquement un scan **4 fois par jour** (toutes les 6h)

---

## Récapitulatif des URLs importantes

| Ce que c'est | URL |
|---|---|
| Ton repo GitHub | `https://github.com/TON_USERNAME/jobsradar-3d` |
| Ton backend Railway | `https://jobsradar-3d-production-XXXX.up.railway.app` |
| Ton dashboard | `https://TON_USERNAME.github.io/jobsradar-3d/` |
| API des offres | `https://...railway.app/api/jobs` |
| API des logs | `https://...railway.app/api/logs` |
| API stats | `https://...railway.app/api/stats` |

---

## Commandes utiles

```bash
# Mettre à jour le code sur le serveur
git add .
git commit -m "Mise à jour"
git push origin main

# Voir les logs Railway (dans le dashboard Railway → onglet Deployments)
```

---

## Troubleshooting

### ❌ Erreur Railway : "Railpack could not determine how to build the app"
**Cause :** Tu as l'ancienne structure avec un dossier `backend/`.  
**Solution :** Utilise ce nouveau ZIP où `main.py` est directement à la racine.

### ❌ Railway déploie mais retourne une erreur 500
1. Va dans Railway → Onglet **Deployments** → clique sur le dernier déploiement
2. Lis les logs d'erreur
3. Cause probable : variable d'environnement manquante

### ❌ Le dashboard dit "Backend non joignable"
1. Vérifie que l'URL Railway est correcte (pas de `/` à la fin)
2. Vérifie que le service Railway est démarré (status vert)
3. Essaie d'ouvrir l'URL du backend directement dans le navigateur

### ❌ Aucune offre après le scan
**Normal les premières fois** — les sites anti-bot bloquent parfois le scraping.  
Le backend génère alors des offres via l'IA comme complément.  
Solution : Lance plusieurs scans sur quelques heures.

### ❌ `"groq": false` dans le backend
La clé GROQ_API_KEY n'est pas configurée dans Railway Variables.  
→ Onglet Variables → Ajoute `GROQ_API_KEY` avec ta clé.

---

## Fonctionnement automatique

```
Chaque 6h (4x/jour) :
  ┌─────────────────────────────────┐
  │  Scraping sur 5 plateformes     │
  │  Indeed · LinkedIn · WTTJ       │
  │  HelloWork · Apec               │
  │         ↓                       │
  │  Enrichissement IA (Groq/Gemini)│
  │  → Descriptions des postes      │
  │  → Tags technologiques          │
  │         ↓                       │
  │  Sauvegarde en base             │
  │  → Nouvelles offres marquées    │
  └─────────────────────────────────┘
```

---

## Coût total : 0€

| Service | Plan | Coût |
|---|---|---|
| GitHub (repo + Pages) | Free | 0€ |
| Railway | Hobby (500h/mois) | 0€ |
| Groq API | Free tier | 0€ |
| Gemini API | Free tier | 0€ |

> Railway offre 500h/mois sur le plan gratuit. Notre backend tourne ~720h/mois.  
> Si tu dépasses, Railway met en pause automatiquement. Pour éviter ça, créer un compte avec **Railway Hobby** (5$/mois) ou utiliser **Render.com** comme alternative gratuite sans limite de temps.

---

*Bon courage pour tes recherches de stage/alternance ! 🚀*
