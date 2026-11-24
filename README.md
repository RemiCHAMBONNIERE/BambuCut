# 🔪 BambuCut — planches de stickers + découpe au traceur (Bambu Lab A1 mini)

Application web **locale ou en ligne** (Streamlit) qui transforme des PNG
transparents en :

1. **planches imprimables** au format exact du plateau (180 × 180 mm par défaut, 300 DPI) ;
2. **fichiers G-code de découpe** pour un porte-lame (drag knife) monté sur une
   Bambu Lab A1 mini ;
3. **aperçus PNG** avec le tracé de découpe en rouge, la croix de calibrage, les
   cotes de chaque sticker et une règle d'échelle.

Un **fond de couleur optionnel** peut être appliqué sous chaque sticker (il remplit
toute la forme découpée, bordure comprise, et s'arrête exactement au tracé). La
couleur de contour se règle **sticker par sticker**, ou d'un seul clic pour tous.

Après génération, un **éditeur interactif** permet de **déplacer** les stickers et
de les **redimensionner directement sur l'aperçu** (poignées d'angle, ratio
conservé, chevauchement autorisé pendant l'édition). « Appliquer l'édition »
régénère les fichiers **en conservant votre disposition** ; un bouton séparé
relance le placement automatique.

Chaque planche dispose aussi d'un **lecteur de trajectoire animé** : la **lame**
est visible dès le départ, posée sur la **croix de calibrage** marquée « départ »,
et suit exactement le G-code, contour par contour, quand on appuie sur **▶ Lire**.
Le **gris** représente les déplacements (lame haute), le **rouge** les coupes, et
le tracé complet reste affiché en pâle. Lecture, pause, contour précédent /
suivant, vitesse (0,5× à 4×) et temps estimé permettent de vérifier l'ordre réel
avant de lancer la découpe. L'animation joue au **temps réel du G-code à 1×**
(déplacements, descentes de lame et coupe inclus) : à 0,5× elle dure deux fois
plus longtemps, à 4× quatre fois moins. Les longueurs de coupe sont affichées
en **cm**. Le lecteur et le G-code partagent la même fonction de calcul : aucun
risque qu'ils se contredisent.

Un **mode simple** est activé par défaut en habillage **Cadeau** : l'interface
se limite à l'import, à la génération, au lecteur animé, aux téléchargements et
au guide. Les réglages avancés, l'éditeur et la longue aide disparaissent ; la
case **✨ Mode simple** dans la barre latérale permet de revenir à l'atelier
complet. En habillage **Sobre**, tous les réglages restent toujours visibles.

Aucune ligne de commande n'est nécessaire pour configurer les planches : tout se
fait à la souris dans le navigateur (import par glisser-déposer, tailles,
quantités, placement multi-planches, téléchargement ZIP).

Un **guide imprimante** est intégré à l'application (bouton **🖨️ Guide
imprimante**) : préparation du plateau, calibration de `Z_CUT` et des offsets,
déroulé d'une découpe, pannes courantes et entretien. Il affiche les réglages
courants et conseille automatiquement si la garde Z ou les vitesses semblent
dangereuses.

---

## 1. Installation

### Prérequis

- **Python 3.10 ou plus récent** (testé avec Python 3.13).
- Windows, macOS ou Linux.
- Une imprimante couleur (pour les planches) et la Bambu Lab A1 mini équipée du
  porte-lame (pour la découpe).

### Installation manuelle (recommandée : environnement local)

N'installez **pas** les paquets dans le Python global, surtout s'il provient du
Microsoft Store : son dossier `site-packages` est très profond et Windows peut
refuser l'installation (`WinError 206`). Créez un environnement local `.venv`
dans le dossier du projet (chemin court) :

**Windows** (PowerShell ou cmd), dans `C:\Git\BambuCut` :

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

**macOS / Linux** :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Le lanceur `Lancer_BambuCut.bat` (ou `.command`) exécute exactement ces étapes
automatiquement : c'est la méthode la plus simple.

> ⚠️ **Erreur `WinError 206 ... nom de fichier trop long`** — elle apparaît
> uniquement si vous lancez `pip install` avec le Python global du Microsoft
> Store. Utilisez le `.venv` du projet comme ci-dessus. Si vous voulez malgré
> tout corriger Windows, ouvrez PowerShell **en administrateur** :
>
> ```powershell
> New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
> ```
>
> puis **redémarrez** Windows. (Équivalent graphique : `gpedit.msc` → Configuration
> ordinateur → Modèles d'administration → Système → Système de fichiers →
> « Activer les chemins longs Win32 ».)

### Lancement

```bash
.venv\Scripts\python.exe -m streamlit run app.py
```

Le navigateur s'ouvre sur <http://localhost:8501>. Pour arrêter : `Ctrl+C`.
Le `.venv` déjà présent dans ce dossier est prêt : vous pouvez aussi simplement
double-cliquer sur `Lancer_BambuCut.bat`.

> Sur Windows, si la commande `python` ouvre le Microsoft Store, utilisez
> `py -3` à la place (comme ci-dessus).

> Le dossier `.venv` est propre à un système d'exploitation. Si vous copiez le
> projet d'un PC Windows vers un Mac (ou l'inverse), supprimez `.venv` avant de
> lancer le raccourci : il sera recréé automatiquement.

---

## 2. Raccourci double-cliquable

### Windows

Le fichier **`Lancer_BambuCut.bat`** fait tout : il crée un environnement Python
local `.venv` au premier lancement, installe les dépendances, puis démarre
l'application et ouvre le navigateur.

1. Double-cliquez sur `Lancer_BambuCut.bat` pour vérifier que tout fonctionne.
2. Clic droit sur `Lancer_BambuCut.bat` → **Envoyer vers** → **Bureau (créer un
   raccourci)**.
3. (Optionnel) Clic droit sur le raccourci → **Propriétés** → **Changer d'icône**
   → choisissez une icône, et renommez-le « BambuCut ».

La première installation peut prendre 1 à 3 minutes ; les suivantes démarrent en
quelques secondes. Laissez la fenêtre noire ouverte pendant l'utilisation.

### macOS

Le fichier **`Lancer_BambuCut.command`** joue le même rôle.

1. Dans le Finder, clic droit sur `Lancer_BambuCut.command` → **Ouvrir** (la
   première fois, macOS demande une confirmation ; cliquez sur **Ouvrir**).
2. Si le fichier n'est pas exécutable, ouvrez le Terminal dans le dossier et
   lancez une fois :
   ```bash
   chmod +x Lancer_BambuCut.command
   ```
3. Pour un vrai raccourci : faites glisser `Lancer_BambuCut.command` sur le
   Bureau en maintenant **Option + Command** (crée un alias), ou ajoutez-le au
   Dock.

---

## 3. Utilisation pas à pas

### Apparence : cadeau ou sobre

Deux habillages sont proposés dans la barre latérale, section **Apparence** :

- **🎁 Cadeau** (par défaut) : fond chaleureux, bandeau d'accueil personnalisé,
  cartes arrondies et boutons colorés. Le prénom est configuré une seule fois
  dans `ui_prefs.json` (il n'est pas modifiable depuis l'interface) ; il apparaît
  dans le bandeau et dans la dédicace du `LISEZMOI.txt` du ZIP.
- **🧰 Sobre** : interface neutre (fond gris clair, angles discrets), pensée pour
  un usage quotidien sans le côté « cadeau ».

Le choix et le prénom sont mémorisés dans `ui_prefs.json`, à côté de
`config.json`. Tout l'habillage est local (CSS intégré, polices système) :
aucune ressource distante n'est chargée, l'application reste utilisable hors
ligne.

En mode **Cadeau**, la case **✨ Mode simple** est cochée au départ : seuls
l'import, la génération, les aperçus animés, les téléchargements et le guide
restent affichés. La décocher révèle l'atelier complet (plateau, calibrage,
bordure, fond, éditeur, aide détaillée). Ce choix est mémorisé lui aussi dans
`ui_prefs.json` (`"simple_mode": true` par défaut).

### Première ouverture : le déballage

Au tout premier lancement en mode **Cadeau**, l'application se présente comme un
cadeau fermé : **« Un cadeau t'attend. »** Rien n'est dévoilé avant l'ouverture.

Le parcours suit l'ouverture réelle, cadeau après cadeau :

1. **Ouvrir le cadeau** : le couvercle s'envole dans une lueur et une pluie de
   confettis, puis le contenu s'affiche. Premier cadeau : **un kit stickers**.
2. **Encore un cadeau →** : la boîte revient avec **« Et c'est pas fini… » /
   « Un deuxième cadeau, rien que pour toi. »**.
3. Deuxième cadeau : **l'atelier BambuCut**, l'application que l'on a sous les
   yeux (« Celui-là, tu l'as déjà entre les mains. »).
4. Nouvel écran d'attente **« Et c'est pas fini… » / « Le dernier, et pas des
   moindres. »**, puis troisième et dernier cadeau : **la Bambu Lab A1 mini**,
   une vraie imprimante 3D qui découpe aussi les stickers, avec le bouton
   **Entrer dans l'atelier →**.

L'intro n'apparaît qu'une seule fois : son état est enregistré dans
`ui_prefs.json` (`"intro_done": true`). Pour la revoir, utilisez **🎁 Revoir
l'unboxing**, tout en bas de la barre latérale (mode Cadeau), ou remettez
`"intro_done": false` dans le fichier. Animations en CSS pur, images SVG
intégrées, aucun accès réseau.

La scène est pensée pour un **téléphone** (ouverture depuis un QR code) :
**plein écran sans cadre**, contenu centré, bouton d'action en bas, cartes
empilées et hauteur du cadre calée sur le viewport. Pour l'ouvrir depuis un
téléphone, lancez Streamlit sur le réseau local :

```bash
streamlit run app.py --server.address 0.0.0.0
```

puis faites pointer le QR code vers `http://<IP-du-PC>:8501` (même Wi-Fi).

#### Personnaliser les textes de l'intro

Toute la copie de l'unboxing est dans **`intro_texts.json`**, à la racine du
projet :

- `tag` : l'étiquette posée sur la boîte (« Pour {name} ») ;
- `initial` : la boîte fermée (sur-titre, titre, sous-titre) ;
- `teasers` : les deux écrans d'attente « Et c'est pas fini… » ;
- `reveals` : les titres affichés après chaque ouverture ;
- `cards` : le contenu des trois cadeaux (titre, texte, pastille) ;
- `buttons` : les libellés des boutons (`open`, `next`, `finish`).

Le prénom est inséré automatiquement avec `{name}`. Pour modifier un texte :

1. ouvrez `intro_texts.json` dans un éditeur de texte (gardez les guillemets et
   les virgules du JSON) ;
2. enregistrez, puis **rechargez la page** (F5, ou tirer vers le bas sur
   téléphone). Aucun redémarrage, aucun build.

Si une clé manque ou si le JSON est cassé, les valeurs par défaut du code
prennent le relais : l'intro s'affiche quand même.

#### Faut-il redéployer ?

En local, non : tout est lu depuis le disque. Le geste dépend seulement de ce
qui change :

| Ce que vous modifiez | Ce qu'il faut faire |
| --- | --- |
| `intro_texts.json` | Enregistrer, puis rafraîchir la page. |
| `bambucut/intro_component/index.html` (style, animation) | Rafraîchir la page (Ctrl+F5 si l'ancienne version reste). |
| Un fichier Python (`app.py`, `bambucut/*.py`) | Redémarrer Streamlit : Ctrl+C, puis `streamlit run app.py`. |
| Une app hébergée sur Streamlit Cloud | Pousser sur le dépôt, puis **Reboot** l'app depuis le tableau de bord. |

Le fichier `intro_texts.json` doit rester à la racine du projet (à côté de
`app.py`) pour être trouvé.

1. **Réglez le plateau** dans la barre latérale (180 × 180 mm, marge 10 mm,
   espacement 3 mm par défaut).
2. **Réglez l'épaisseur de bordure** (`2.5` mm par défaut) : c'est la marge
   blanche ajoutée autour de la silhouette de chaque sticker.
3. **Choisissez éventuellement un fond de couleur** dans « 🎨 Fond & cotes » :
   la couleur remplit la forme découpée (bordure comprise) et s'arrête au tracé.
   Les cases « Afficher les cotes » et « Afficher la règle d'échelle » ajoutent
   les dimensions et une barre de 50 mm sur l'aperçu (jamais sur le PDF).
4. **Vérifiez le calibrage** : repère `X = 10 / Y = 10 mm`, offsets buse → lame,
   `Z_CUT`, `Z_TRAVEL`, vitesses.
5. **Glissez-déposez un ou plusieurs PNG** dans la zone d'import.
6. Pour chaque image :
   - choisissez **Largeur cible** ou **Hauteur cible** ;
   - saisissez la dimension en mm (le ratio est conservé, l'autre dimension est
     calculée et affichée en direct) ;
   - réglez la **quantité** ;
   - choisissez le **Contour** : « Comme le réglage global », « Couleur
     personnalisée » (avec son nuancier) ou « Sans fond (bordure papier) » ;
   - l'icône 🗑️ retire l'image de la liste.
7. Utilisez au besoin la barre **🎨 Couleur de contour** : « Couleur pour tous »
   applique le nuancier à tous les stickers, « Suivre le global » et « Sans fond »
   remettent tout d'un coup.
8. Cliquez sur **🚀 Générer les planches**.
9. **Ajustez la planche** (facultatif) : dans la section « ✏️ Déplacer /
   redimensionner sur l'aperçu » :
   - **glissez un sticker** pour le déplacer (il reste dans la zone utile) ;
   - glissez ses **coins rouges** pour le redimensionner (ratio conservé) ;
     l'agrandissement va jusqu'à la zone utile : le sticker glisse tout seul
     pour rester dans les marges ;
   - le chevauchement est autorisé pendant l'édition, un avertissement le signale ;
   - cliquez sur **✓ Appliquer l'édition** : les dimensions sont reportées dans
     la liste et la planche est régénérée **en conservant vos positions** ;
   - **♻️ Recalculer le placement automatique** abandonne la disposition manuelle
     et replace tout proprement (sans chevauchement, espacement respecté).
10. **Vérifiez le trajet** sous chaque planche : la lame démarre sur la croix de
    calibrage (« départ »). « ▶ Lire » lance l'animation, « ⏸ Pause » l'arrête,
    « ⏮ Préc. » / « ⏭ Suiv. » sautent d'un contour à l'autre, et le sélecteur de
    vitesse permet d'accélérer. Le gris est un déplacement lame haute, le rouge
    une coupe. Le temps affiché correspond à la durée réelle du trajet à 1×
    (déplacements, descentes et coupe) ; à 0,5× l'animation dure deux fois plus
    longtemps. Les longueurs sont en cm.
11. Téléchargez :
    - **tout le ZIP** avec le bouton « Tout télécharger (.ZIP) » ;
    - ou les fichiers planche par planche.

La liste et les réglages sont conservés quand vous modifiez une quantité ou une
taille. Les fichiers déjà générés restent disponibles, avec un avertissement si
vous changez quelque chose entre-temps.

### Contenu du ZIP

Pour chaque planche `X` :

| Fichier | Rôle |
|---|---|
| `planche_X_impression.pdf` | planche à imprimer à **100 %** (page de 180 × 180 mm exactement) |
| `planche_X_decoupe.gcode` | programme de découpe pour le porte-lame |
| `planche_X_previsu.png` | aperçu : stickers, bordure, contour rouge, plateau, croix |
| `config_utilisee.json` | copie des réglages ayant servi à la génération |
| `LISEZMOI.txt` | rappel des consignes d'impression et de sécurité |

---

## 4. Impression : à l'échelle 100 %

- Ouvrez le PDF dans Acrobat Reader, Chrome, Aperçu ou équivalent.
- Choisissez **Taille réelle / 100 %**, et désactivez **« Ajuster à la page »**
  ou **« Réduire les pages surdimensionnées »**.
- Imprimez sur une feuille d'au moins 180 × 180 mm. Si la feuille est plus
  grande (A4, Letter), gardez 100 % : la planche restera en haut à gauche.
- Vérifiez avec une règle : la croix doit être à **10 mm du bord gauche** et
  **10 mm du bord inférieur**. C'est votre contrôle d'échelle avant de découper.

Le PDF ne contient **que le visuel et la croix de calibrage** : le tracé rouge
n'est présent que dans l'aperçu et le G-code. La bordure blanche est simplement
du papier non imprimé et non découpé autour du sticker.

---

## 5. Découpe : calibration et sécurité

> ⚠️ **À lire avant la première découpe.** Un porte-lame est un outil tranchant
> monté sur une machine qui peut se déplacer vite. Vous êtes responsable de la
> sécurité de votre machine et de votre poste de travail.

### Mise en place

1. Montez le porte-lame, lame **relevée** ou démontée pour les premiers tests.
2. Homez la machine depuis l'écran de la Bambu Lab A1 mini (le G-code ne home
   **jamais** Z, pour ne pas planter la lame dans le plateau).
3. Établissez la référence Z : descendez manuellement jusqu'à ce que la pointe
   de lame effleure la feuille, puis reportez cette hauteur dans `Z_CUT`.
   `Z_TRAVEL` doit être quelques millimètres au-dessus (`18.2` par exemple).
4. Mesurez le décalage entre la buse et la pointe de lame, et reportez-le dans
   **Offset X / Offset Y**.
5. Imprimez une planche, posez-la sur le plateau en alignant la croix imprimée
   avec la position `X = 10 / Y = 10 mm`, puis bloquez la feuille (adhésif ou
   tapis).
6. Faites un **test à vide** : lancez le G-code avec `Z_CUT` remonté de quelques
   millimètres (ou sans papier) et vérifiez que la trajectoire reste dans la
   feuille et ne heurte rien.

### Ce que fait le G-code

- `G21` (millimètres) + `G90` (coordonnées absolues), origine `(0,0)` en
  **bas à gauche** du plateau ;
- premier déplacement vers la **croix de calibrage** (`X=10 / Y=10` par défaut)
  avant la première coupe, pour correspondre à la lame affichée dans l'aperçu ;
- **aucune** commande de chauffe (`M104`, `M109`, `M140`, `M190`) ;
- **aucune** extrusion (pas de paramètre `E`) ;
- **aucun** nivellement automatique (`G29`) ni homing Z ;
- descente de lame à `Z_CUT`, suivi du contour lissé à `FEED_RATE_CUT`, remontée
  à `Z_TRAVEL` entre chaque contour ;
- offsets buse → lame appliqués à toutes les coordonnées de coupe ;
- fin : `Z = Z_TRAVEL + 20`, puis `G0 Y175` pour avancer le plateau et retirer la
  feuille.

L'option `G28 X Y` (décochée par défaut) ajoute un homing X/Y au début, sans
toucher à Z. À utiliser seulement si la machine n'est pas déjà homée.

> La Bambu A1 mini est une imprimante : selon votre firmware et votre méthode de
> lancement, un fichier `.gcode` brut peut nécessiter une procédure particulière
> (carte SD, outil de contrôle, etc.). N'ajoutez **jamais** de préchauffage ou de
> nivellement automatique à ce fichier pour le faire accepter : cela irait à
> l'encontre du but recherché et pourrait endommager la lame ou le plateau.

### Réglages de départ

| Paramètre | Valeur par défaut | Rôle |
|---|---|---|
| `BORDER_THICKNESS_MM` | 2.5 mm | bordure autour de chaque visuel (blanche ou couleur de fond) |
| `Fond de couleur` | désactivé | remplit toute la forme découpée, bordure comprise |
| `Contour par sticker` | suit le global | couleur propre ou « sans fond » pour chaque sticker |
| `Éditeur d'aperçu` | — | déplacement + redimensionnement à la souris, disposition conservée |
| `Cotes / échelle` | activées | annotations d'aperçu uniquement, pas d'impression |
| `Z_CUT` | 14.2 mm | hauteur de coupe (à adapter à votre porte-lame) |
| `Z_TRAVEL` | 18.2 mm | hauteur lame relevée |
| `FEED_RATE_CUT` | 1200 mm/min | vitesse de tracé |
| `FEED_RATE_TRAVEL` | 3000 mm/min | vitesse de déplacement |
| Plunge feed | 600 mm/min | vitesse de descente de la lame |
| Marge / espacement | 10 / 3 mm | zone utile et écart entre stickers |

Ces hauteurs Z sont des exemples : elles dépendent entièrement de la géométrie
de votre support de lame. **Mesurez les vôtres.**

---

## 6. Configuration persistante

Les boutons **💾 Enregistrer** et **📂 Charger** écrivent et relisent
`config.json` à la racine du projet. Le fichier est aussi téléchargeable depuis
la barre latérale. Il contient le plateau, les marges, la bordure, le lissage,
le calibrage, les offsets, Z et les vitesses. **Au démarrage, `config.json` est
chargé automatiquement** ; le bouton « Charger » sert à le relire après une
modification externe.

Si le fichier est absent, l'application utilise les valeurs par défaut. S'il est
édité à la main, les valeurs sont nettoyées et bornées automatiquement.

L'apparence (thème **Cadeau** / **Sobre**, prénom affiché, intro vue et mode
simple) est stockée à part dans `ui_prefs.json`, pour ne pas mélanger les
préférences d'affichage avec les réglages machine du `config.json` :

```json
{
  "style": "gift",
  "recipient": "Adèle",
  "intro_done": true,
  "simple_mode": true
}
```

Modifier `simple_mode` à la main fonctionne aussi : rechargez la page pour que
le changement soit pris en compte.

---

## 7. Fonctionnement technique

- **Silhouette** : canal alpha du PNG ; si l'image n'a pas de transparence, son
  rectangle extérieur est utilisé.
- **Redimensionnement** : 300 DPI (11,811 px/mm), ratio strictement conservé,
  rééchantillonnage Lanczos.
- **Bordure** : buffer géométrique Shapely de `BORDER_THICKNESS_MM` (angles
  arrondis ou vifs), trous internes comblés pour n'avoir qu'un contour extérieur.
  Les morceaux réellement séparés (ex. un point détaché) restent des contours
  fermés distincts, tous découpés.
- **Fond de couleur** : la forme découpée est remplie avec la couleur choisie
  (bordure comprise), puis le visuel est composé par-dessus en mode « source
  over ». La couleur ne dépasse donc jamais le tracé de coupe. La couleur est
  résolue par sticker (`inherit` → réglage global, `custom` → couleur propre,
  `none` → bordure papier).
- **Éditeur d'aperçu** : composant Streamlit local (`bambucut/editor_component/`)
  écrit en HTML/JS, sans npm ni accès réseau. Il affiche la planche à l'échelle,
  renvoie un **facteur d'échelle par image** et un **centre (x, y) par sticker**
  déplacé, puis Python convertit le tout (`scaled_size_mm`, `sheets_from_layout`)
  en dimensions cibles et en disposition manuelle. Cette disposition est
  mémorisée tant que la liste et les quantités ne changent pas.
- **Cotes** : la taille finie de chaque sticker (bordure comprise) est dessinée
  sur l'aperçu, avec une barre d'échelle ; ces annotations ne sont jamais
  imprimées dans le PDF.
- **Lissage** : simplification Douglas-Peucker (tolérance réglable) pour éviter
  les micro-saccades de la machine.
- **Placement** : algorithme **MaxRects / Best-Short-Side-Fit**, multi-planches,
  rotation à 90° optionnelle (l'image **et** son contour tournent ensemble),
  espacement garanti entre contours.
- **PDF** : ReportLab, page de 180 × 180 mm, images à 300 DPI, croix de
  calibrage vectorielle.
- **G-code** : nombres à 3 décimales maximum, commentaires ASCII, contrôle de
  sécurité intégré qui refuse toute commande interdite.
- **Trajet animé** : `iter_cut_contours()` fournit les contours (offsets
  appliqués) dans l'ordre exact du G-code, en comptant le premier déplacement
  depuis le repère de calibrage. Le lecteur (`bambucut/cut_component/`)
  superpose ces tracés sur l'aperçu et les anime en SVG/CSS via l'API Web
  Animations. La **lame** et le repère de « départ » sont des calques HTML/CSS
  positionnés depuis les coordonnées SVG, à taille fixe en pixels : la lame
  reste visible même sur mobile. Le composant ne renvoie aucune valeur à
  Streamlit. Lecture, pause, saut de contour et vitesse sont pilotés localement,
  sans npm ni accès réseau.

### Structure du projet

```
BambuCut/
├── app.py                     # interface Streamlit (toute l'UI)
├── bambucut/
│   ├── config.py              # config.json (lecture/écriture, bornes)
│   ├── cut_player.py          # pont Streamlit <-> lecteur de trajectoire
│   ├── cut_component/         # lecteur de coupe animé (HTML/CSS/JS local)
│   ├── editor.py              # pont Streamlit <-> éditeur d'aperçu
│   ├── editor_component/      # composant HTML/JS (déplacement + redimensionnement)
│   ├── geometry.py            # PNG -> silhouette -> bordure -> contour
│   ├── gcode.py               # génération + contrôle sécurité du G-code
│   ├── guide.py               # textes du guide imprimante (calibration, pannes)
│   ├── intro.py               # pont Streamlit <-> écran d'accueil (unboxing)
│   ├── intro_component/       # scène d'ouverture du cadeau (HTML/CSS/JS local)
│   ├── models.py              # dataclasses (config, stickers, placements)
│   ├── packing.py             # MaxRects multi-planches
│   ├── pdf_export.py          # PDF 300 DPI à l'échelle 1:1
│   ├── preview.py             # aperçu PNG (rouge = découpe)
│   └── theme.py               # habillages cadeau / sobre (CSS local, préférences)
├── .streamlit/config.toml     # thème et réglages Streamlit
├── outils/
│   └── qr_cadeau.py           # carte A6 + QR code à coller sur le carton
├── requirements.txt
├── requirements-outils.txt    # dépendances du générateur de QR (segno)
├── config.json                # réglages machine sauvegardés (créé/modifié par l'app)
├── ui_prefs.json              # apparence + prénom + intro vue + mode simple
├── selftest.py                # tests automatiques de la chaîne complète
├── Lancer_BambuCut.bat        # raccourci Windows
├── Lancer_BambuCut.command    # raccourci macOS
└── README.md
```

### Test automatique

```bash
python selftest.py
```

Le script crée des images de synthèse, vérifie la géométrie (visuel inclus dans
la coupe, bordure, rotation), le fond de couleur (remplissage limité au contour,
une couleur par sticker), la résolution des modes de contour, le passage
échelle → dimension de l'éditeur, la disposition manuelle (aller-retour des
positions et rotations, recadrage dans la zone utile, détection des
chevauchements), le placement (pas de chevauchement, espacement), la taille du
PDF, l'absence de commandes interdites dans le G-code et les coordonnées, la
cohérence du lecteur animé avec le G-code (mêmes contours, mêmes offsets,
déplacements entre contours) et le protocole de son composant, ainsi que
l'habillage (préférences `ui_prefs.json` avec `simple_mode`, CSS des deux
thèmes, échappement du prénom et dédicace du ZIP) et l'écran d'ouverture
(`intro_component/index.html`, protocole du composant, préférence
`intro_done`). Les fichiers de contrôle sont écrits dans `_selftest_out/`.

---

## 8. Dépannage

| Problème | Solution |
|---|---|
| `WinError 206 ... nom de fichier trop long` pendant `pip install` | vous installez dans le Python global du Microsoft Store. Utilisez le `.venv` du projet (`Lancer_BambuCut.bat`), ou activez les chemins longs (voir §1). |
| `streamlit n'est pas reconnu` | utilisez `.venv\Scripts\python.exe -m streamlit run app.py`, ou le lanceur qui crée le `.venv`. |
| `ModuleNotFoundError: cv2 / shapely` | relancez `python -m pip install -r requirements.txt` avec le **même** Python que celui qui lance Streamlit. |
| Le navigateur ne s'ouvre pas | ouvrez manuellement <http://localhost:8501>. |
| Port 8501 déjà utilisé | fermez l'autre instance, ou lancez `python -m streamlit run app.py --server.port 8502`. |
| Erreur de chemin trop long sous Windows | lancez `Lancer_BambuCut.bat` (le `.venv` est au même endroit) ; évitez d'installer dans un dossier très profond. |
| Le PDF est plus petit que prévu | impression à 100 %, « ajuster à la page » désactivé. Mesurez la croix. |
| La lame ne coupe pas | vérifiez le sens de la lame (elle doit pivoter librement), descendez `Z_CUT` par pas de 0,1 mm, ralentissez `FEED_RATE_CUT`. |
| La lame traverse le papier | remontez `Z_CUT`, vérifiez la planéité du plateau et la fixation de la feuille. |
| Un sticker dépasse la zone utile | réduisez sa dimension, la bordure ou la marge. |
| Le G-code est refusé par la machine | vérifiez votre procédure de lancement ; n'ajoutez pas de chauffe ni de `G29`. |
| L'aperçu affiche un damier sous le sticker | c'est attendu : le damier visualise la transparence (papier). |
| L'éditeur d'aperçu ne s'affiche pas | rechargez la page (F5) ; le composant est servi localement par Streamlit, aucun accès Internet n'est requis. |
| Le lecteur de trajectoire reste vide | rechargez la page (Ctrl+F5) ; régénérez les planches si l'aperçu vient d'une version ancienne de l'application. |
| Les réglages avancés ont disparu | vous êtes en mode **Cadeau / Mode simple** : décochez **✨ Mode simple** dans la barre latérale. |
| Les stickers se chevauchent dans l'éditeur | c'est autorisé pendant l'édition ; l'avertissement disparaît après **♻️ Recalculer le placement automatique**, ou en les déplaçant dans l'éditeur. |
| Le lien du QR met du temps à répondre | l'app en ligne était endormie : attendez 30 à 60 secondes, la page se charge ensuite normalement. |
| Les réglages machine ont disparu en ligne | le serveur a redémarré. Restaurez le `config.json` téléchargé depuis le **guide imprimante** (onglet d'accueil du guide). |
| Le QR ne se scanne pas | imprimez à 100 %, vérifiez le contraste, évitez le scotch brillant et testez avec plusieurs téléphones. |

---

## 9. Limites connues

- Le PDF ne gère qu'une page par planche et une seule feuille par planche.
- L'éditeur d'aperçu déplace et redimensionne les stickers, mais un
  redimensionnement s'applique à **toutes les copies d'un même sticker** (même
  image) : leurs positions restent indépendantes.
- La disposition manuelle est abandonnée si la liste des images ou les quantités
  changent : le placement automatique reprend la main (un message le signale).
- Les très petits détails (< 0,5 mm²) sont ignorés volontairement pour éviter
  que la lame ne suive des poussières de pixels.
- Les stickers peuvent avoir plusieurs contours (morceaux séparés) ; chacun est
  découpé, mais la bordure est calculée autour de chaque morceau.
- La découpe suit un polygone : les dégradés très doux et les zones semi-
  transparentes sont traités au seuil alpha de 50 %.
- En local, rien ne sort de l'ordinateur. En ligne, les images transitent par le
  serveur le temps de la session (elles ne sont pas écrites dans le dépôt), et
  les réglages `config.json` / `ui_prefs.json` vivent sur ce serveur.

---

## 10. Guide imprimante intégré

Le bouton **🖨️ Guide imprimante** (barre latérale ou bas de la page d'aide)
ouvre une vue dédiée, en cinq onglets :

| Onglet | Contenu |
|---|---|
| **Préparer** | plateau, porte-lame, origine X/Y, alignement de la feuille, test à vide, check-list interactive |
| **Calibrer** | méthode papier pour `Z_CUT`, réglage des offsets X/Y avec schéma, contrôle de l'échelle |
| **Découper** | déroulé complet, ce que fait le G-code, consignes de surveillance |
| **Pannes** | lame qui ne coupe pas, bords déchirés, décalage, feuille qui se soulève, G-code refusé… |
| **Entretien** | nettoyage, changement de lame, stock, bonnes habitudes |

Le guide lit vos réglages courants (Z, offsets, vitesses), signale une garde
Z trop faible ou une vitesse de coupe élevée, et permet de **télécharger** ou
**restaurer** `config.json`. La check-list n'est pas enregistrée : elle est à
refaire à chaque session, volontairement.

---

## 11. Déployer en ligne et QR code du carton

### Streamlit Community Cloud

L'application est prête pour un hébergement gratuit sur
[share.streamlit.io](https://share.streamlit.io) :

1. poussez le dossier sur GitHub (`.venv/` et `_selftest_out/` sont déjà ignorés) ;
2. **New app** → choisissez le dépôt, la branche et `app.py` ;
3. aucun secret n'est nécessaire, `requirements.txt` suffit.

À savoir avant de mettre le lien sur un carton :

- **Réveil** : une app gratuite s'endort après une période sans visite. Le
  premier scan peut mettre 30 à 60 secondes ; c'est normal.
- **Réglages** : `config.json` est écrit sur le serveur. Un redémarrage peut
  remettre les valeurs du dépôt. Après la calibration, téléchargez le fichier
  depuis le guide et gardez-le ; rechargez-le si besoin.
- **Intro** : `ui_prefs.json` est partagé par tous les visiteurs. Une fois
  l'unboxing terminé, il ne se rejoue pas pour les suivants — pratique pour un
  cadeau à une seule personne.
- **Confidentialité** : le lien est public. Les images importées restent en
  mémoire le temps de la session et ne sont pas écrites dans le dépôt.
- **Thème** : le sélecteur Cadeau / Sobre reste disponible dans la barre
  latérale.

### Carte QR à coller sur le premier carton

Un petit script génère le QR code et une carte A6 prête à imprimer (page A4
avec traits de coupe) :

```bash
python -m pip install -r requirements-outils.txt
python outils/qr_cadeau.py "https://votre-app.streamlit.app" --nom "Adèle"
```

Fichiers produits à côté du script (ou dans `--sortie`) :

- `qr_cadeau.pdf` — carte A6 centrée sur une page A4, avec traits de coupe ;
- `qr_cadeau_qr.png` — le QR seul, pour l'intégrer à une étiquette ou à un
  logiciel de mise en page ;
- `qr_cadeau_qr.svg` — version vectorielle, pour une impression nette.

Conseils : imprimez à **100 %**, scannez la carte avec le téléphone avant de la
coller, et écrivez l'URL en petit sous le QR (secours si l'appareil photo fait
des siennes). Le QR doit rester bien à plat et ne pas être recouvert de scotch
brillant.

### Rester en réseau local (sans hébergement)

Si vous préférez ne rien publier, lancez l'app sur le PC qui reste allumé :

```bash
.venv\Scripts\python.exe -m streamlit run app.py --server.address 0.0.0.0
```

Le téléphone doit être sur le **même Wi-Fi**, puis ouvrez
`http://<IP-du-PC>:8501` (l'IP locale s'affiche dans la fenêtre Streamlit ou via
`ipconfig`). Le QR pointe alors vers cette adresse : réservez l'IP dans le
routeur pour qu'elle ne change pas, et gardez le PC allumé.

Bon courage, et faites toujours un **test à vide** avant la première vraie
découpe. 🔪
