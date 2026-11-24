"""Contenu du guide imprimante (textes purs, testables sans Streamlit).

Le guide est affiche dans une vue dediee de l'application. Il reprend la
procedure de calibration du README, avec des valeurs lues dans la configuration
courante pour eviter de recopier des chiffres obsoletes.
"""

from __future__ import annotations

from pathlib import Path

from .models import MachineConfig

# Le SVG ci-dessous est la source du schema affiche dans l'onglet Calibrer.
# Il est rasterise dans assets/offset_xy.png : Streamlit retire les formes des
# SVG injectes en markdown, et une image reste nette et responsive partout.
OFFSET_IMAGE = Path(__file__).resolve().parent / "assets" / "offset_xy.png"

GUIDE_TITLE = "🖨️ Gérer l'imprimante"
GUIDE_SUBTITLE = (
    "Bambu Lab A1 mini + porte-lame : préparation, calibration, découpe et "
    "entretien. À parcourir une fois avant la première coupe, puis à garder "
    "sous la main."
)

SAFETY = (
    "Une lame montée sur une machine qui se déplace vite. Gardez les mains et "
    "les objets loin du plateau pendant un cycle, commencez toujours par un "
    "test à vide, et gardez le bouton d'arrêt à portée."
)

SERVER_TIP = (
    "Version en ligne : `config.json` est stocké sur le serveur. Un redémarrage "
    "de l'application peut remettre les réglages par défaut. Après la "
    "calibration, téléchargez le fichier pour le garder, et rechargez-le si "
    "besoin."
)

PREPARE = """
### La mise en place, dans l'ordre

1. **Plateau propre et plat.** Retirez les résidus, dépoussiérez, et posez un
   tapis fin ou préparez la feuille. Une miette sous le papier suffit à faire
   rater une découpe.
2. **Porte-lame installé selon sa notice.** Machine éteinte et buse froide.
   Pour les premiers essais, montez la lame **relevée** ou retirez-la.
3. **Lame libre.** La pointe doit pouvoir pivoter librement dans son logement.
   Une lame qui force arrache le papier au lieu de le couper.
4. **Origine X/Y.** Homez X/Y **depuis l'écran** de la machine. Le G-code ne
   home jamais Z, pour ne pas planter la lame.
5. **Garde au-dessus de la coupe.** `Z_TRAVEL` doit dépasser `Z_CUT` d'au moins
   2 mm (3 à 4 mm recommandé).
6. **Feuille alignée.** Imprimez à **100 %**, posez la feuille avec la croix de
   calibrage sur `X = 10 / Y = 10 mm`, puis fixez les quatre bords avec de
   l'adhésif repositionnable ou un tapis.
7. **Test à vide.** Remontez `Z_CUT` de 3 mm (ou retirez le papier) et vérifiez
   que la trajectoire reste dans la feuille et ne heurte rien.

> La première planche se fait toujours **sans papier** ou avec la lame bien
> haute. On ne découvre pas une collision en même temps qu'une découpe.
"""

CHECKLIST = (
    "Le porte-lame est monté et la lame est relevée pour le premier test.",
    "X/Y sont homés depuis l'écran (pas de homing Z).",
    "Z_CUT et Z_TRAVEL sont vérifiés, avec au moins 2 mm de garde.",
    "La feuille est alignée sur la croix et fixée aux quatre bords.",
    "Un test à vide a été fait, sans collision.",
    "Personne ne touche la machine et l'arrêt est accessible.",
)

CALIBRATE = """
### 1. Trouver `Z_CUT` (méthode papier)

1. Homez Z **depuis l'écran** de la machine, pas avec le G-code.
2. Posez une chute de papier sur le plateau, à l'endroit de la découpe.
3. Descendez l'axe par petits pas jusqu'à ce que la pointe marque à peine le
   papier.
4. Notez le Z affiché. Si vous avez pris le zéro sur le dessus du papier,
   ajoutez son épaisseur (environ 0,1 mm) pour obtenir la hauteur de coupe.
5. Reportez la valeur dans **Z de coupe**, puis mettez **Z de déplacement**
   3 à 4 mm au-dessus.
6. Coupez un petit carré de test : s'il ne traverse pas, descendez de 0,1 mm ;
   s'il marque le support, remontez de 0,1 mm.

### 2. Régler les offsets X / Y

Le G-code **ajoute** `Offset X` et `Offset Y` à chaque coordonnée de coupe.
L'offset est donc la correction qui amène la lame exactement sur le tracé.

1. Coupez un petit repère à un endroit connu (le carré de test suffit).
2. Mesurez l'écart entre le tracé voulu et le tracé obtenu.
3. Si la lame coupe **trop à droite**, diminuez `Offset X` de l'écart ;
   **trop à gauche**, augmentez-le.
4. Si elle coupe **trop vers l'arrière**, diminuez `Offset Y` ; **trop vers
   l'avant**, augmentez-le.
5. Recoupez, ajustez par pas de 0,5 mm, puis affinez à 0,1 mm.

La croix imprimée sert à vérifier l'**échelle** (100 %), pas à régler les
offsets : ceux-ci compensent uniquement l'écart entre la buse et la pointe de
lame.

> Les valeurs `14.2 / 18.2 mm` du projet sont des exemples. Elles dépendent
> entièrement de la géométrie de votre porte-lame : mesurez les vôtres.
"""

OFFSET_SVG = """
<svg viewBox="0 0 560 250" role="img" aria-label="Schéma des offsets X et Y"
     style="width:100%;height:auto;display:block;margin:0.4rem auto 0.9rem;
            max-width:620px;border-radius:16px;">
  <rect x="1" y="1" width="558" height="248" rx="16" fill="#FFFBF7"
        stroke="#F3D9C9" stroke-width="1.5"/>
  <text x="24" y="32" font-family="Georgia, serif" font-size="17"
        fill="#332833">Vue de dessus</text>
  <text x="24" y="52" font-family="Arial, sans-serif" font-size="11"
        fill="#7D6A72">Le point rouge est la découpe obtenue ; le viseur, la position voulue.</text>

  <line x1="96" y1="196" x2="470" y2="196" stroke="#E7C8B7" stroke-width="1"
        stroke-dasharray="4 5"/>
  <line x1="96" y1="196" x2="96" y2="82" stroke="#E7C8B7" stroke-width="1"
        stroke-dasharray="4 5"/>
  <text x="462" y="216" font-family="Arial, sans-serif" font-size="11"
        fill="#7D6A72">X</text>
  <text x="80" y="90" font-family="Arial, sans-serif" font-size="11"
        fill="#7D6A72">Y</text>

  <circle cx="96" cy="196" r="13" fill="none" stroke="#332833" stroke-width="2"/>
  <line x1="83" y1="196" x2="109" y2="196" stroke="#332833" stroke-width="1.5"/>
  <line x1="96" y1="183" x2="96" y2="209" stroke="#332833" stroke-width="1.5"/>
  <text x="56" y="226" font-family="Arial, sans-serif" font-size="11"
        fill="#7D6A72">position voulue</text>

  <line x1="96" y1="196" x2="360" y2="196" stroke="#FF7A59" stroke-width="2"
        stroke-dasharray="6 4"/>
  <line x1="360" y1="196" x2="360" y2="112" stroke="#FF5C8A" stroke-width="2"
        stroke-dasharray="6 4"/>
  <text x="214" y="188" font-family="Arial, sans-serif" font-size="12"
        font-weight="bold" fill="#C9431F">Offset X &gt; 0</text>
  <text x="370" y="160" font-family="Arial, sans-serif" font-size="12"
        font-weight="bold" fill="#C2405F">Offset Y &gt; 0</text>

  <circle cx="360" cy="112" r="9" fill="#FF5C8A"/>
  <circle cx="360" cy="112" r="3.5" fill="#FFFFFF"/>
  <text x="378" y="104" font-family="Arial, sans-serif" font-size="12"
        fill="#332833">découpe obtenue</text>

  <text x="24" y="240" font-family="Arial, sans-serif" font-size="10.5"
        fill="#7D6A72">Découpe trop à droite / trop en arrière ? Diminuez les offsets.
  Puis recoupez et affinez par 0,1 mm.</text>
</svg>
"""

CUT = """
### Une découpe, pas à pas

1. **Imprimez** le PDF à **100 % / taille réelle**, sans « ajuster à la page ».
   Vérifiez la croix de calibrage avec une règle.
2. **Posez** la feuille : croix sur `X = 10 / Y = 10 mm`, quatre bords fixés.
3. **Homez X/Y** depuis l'écran de la machine.
4. **Lancez le G-code** selon votre procédure habituelle (carte SD, outil de
   contrôle, etc.). Le fichier ne chauffe pas, n'extrude pas et ne nivele pas.
5. **Surveillez le premier contour.** Une main sur l'arrêt, pas de téléphone,
   pas de chat sur le plateau.
6. **Attendez l'arrêt complet** : le programme remonte la lame puis avance le
   plateau pour retirer la feuille.
7. **Retirez la feuille à plat**, laissez la lame revenir au repos, puis
   décollez le papier support.

### Ce que fait le fichier

- `G21` + `G90` : millimètres et coordonnées absolues, origine en bas à gauche.
- **Aucune** chauffe, **aucune** extrusion, **aucun** nivellement automatique.
- Descente à `Z_CUT`, contour lissé à la vitesse de coupe, remontée à
  `Z_TRAVEL` entre chaque contour.
- Fin : `Z = Z_TRAVEL + 20`, puis avance du plateau pour retirer la feuille.

> N'ajoutez jamais de préchauffage, d'extrusion ou de `G29` pour faire accepter
> le fichier par la machine : cela irait contre le but recherché et pourrait
> endommager la lame ou le plateau.
"""

TROUBLESHOOTING = (
    (
        "La lame ne traverse pas le papier partout",
        "Z trop haut, plateau pas plan ou feuille qui gondole. Descendez "
        "`Z_CUT` de 0,1 mm, vérifiez les quatre coins, recollez la feuille et "
        "refaites un carré de test.",
    ),
    (
        "La lame marque le tapis ou traverse le support",
        "`Z_CUT` trop bas. Remontez de 0,1 mm, puis refaites un test sur une "
        "chute avant de lancer une vraie planche.",
    ),
    (
        "Bords déchirés ou poils de papier",
        "Lame émoussée, bloquée dans son logement, ou vitesse trop élevée. "
        "Changez la lame, vérifiez qu'elle pivote librement et réduisez la "
        "vitesse de coupe (800 à 1 000 mm/min pour commencer).",
    ),
    (
        "La découpe est décalée par rapport à l'impression",
        "Offsets X/Y à ajuster, feuille mal alignée ou adhésif insuffisant. "
        "Vérifiez la croix, refaites un repère et ajustez les offsets par "
        "0,5 mm.",
    ),
    (
        "Un sticker se soulève pendant la coupe",
        "Bordure trop fine ou papier bombé. Augmentez la bordure (3 à 4 mm), "
        "aplatissez la feuille et ajoutez de l'adhésif sur les bords.",
    ),
    (
        "La coupe sort de la feuille",
        "Marge, offsets ou rotation. Lisez l'avertissement affiché après la "
        "génération et réduisez la taille du sticker concerné.",
    ),
    (
        "Le G-code est refusé par la machine",
        "N'ajoutez ni chauffe, ni extrusion, ni `G29` pour le faire passer. "
        "Suivez la procédure de lancement de votre firmware et vérifiez que le "
        "fichier est bien celui de la découpe.",
    ),
    (
        "Les réglages ont disparu",
        "En ligne, le serveur peut redémarrer et repartir du `config.json` du "
        "dépôt. Téléchargez vos réglages après calibration et rechargez-les "
        "depuis le guide.",
    ),
)

MAINTENANCE = """
### Après chaque séance

- Relevez la lame, coupez l'alimentation et retirez les chutes de papier.
- Essuyez le plateau et le dessous du porte-lame : les poussières de papier
  finissent par fausser la hauteur de coupe.
- Rangez le porte-lame avec la lame rentrée ou démontée, hors de portée des
  enfants.

### Quand un bord s'effiloche

- Changez la lame : c'est le premier suspect, avant les réglages.
- Vérifiez le serrage du porte-lame et l'absence de jeu.
- Recontrôlez `Z_CUT` sur une chute de papier : l'épaisseur du support peut
  varier d'un rouleau à l'autre.
- Soufflez la zone de coupe ; une lame qui traîne des poussières ne coupe plus
  proprement.

### Le stock utile

- Deux ou trois lames de rechange, pour ne pas interrompre une série.
- De l'adhésif repositionnable ou un tapis fin.
- Des feuilles sticker de rechange, et une règle pour vérifier la croix.

### Bon à savoir

- Les images importées ne sont pas écrites dans le dépôt : elles restent en
  mémoire le temps de la session.
- Le G-code ne home jamais Z et ne chauffe jamais la buse : la sécurité de la
  hauteur repose sur votre calibration et sur le test à vide.
"""

TABS = ("Préparer", "Calibrer", "Découper", "Pannes", "Entretien")


def settings_summary(cfg: MachineConfig) -> list[tuple[str, str, str]]:
    """Quatre valeurs a afficher en haut du guide (libelle, valeur, aide)."""
    return [
        (
            "Z de coupe",
            f"{cfg.z_cut_mm:.2f} mm",
            "Hauteur de la lame pendant le tracé.",
        ),
        (
            "Z de déplacement",
            f"{cfg.z_travel_mm:.2f} mm",
            "Hauteur de la lame entre deux contours.",
        ),
        (
            "Offsets X / Y",
            f"{cfg.offset_x_mm:+.2f} / {cfg.offset_y_mm:+.2f} mm",
            "Correction buse → lame ajoutée à chaque point du G-code.",
        ),
        (
            "Vitesse de coupe",
            f"{cfg.feed_cut} mm/min",
            f"Déplacement {cfg.feed_travel} mm/min · descente "
            f"{cfg.plunge_feed} mm/min.",
        ),
    ]


def settings_advice(cfg: MachineConfig) -> list[tuple[str, str]]:
    """Conseils contextuels (niveau, texte), sans dupliquer les erreurs."""
    advice: list[tuple[str, str]] = []
    if cfg.problems():
        return advice
    guard = cfg.z_travel_mm - cfg.z_cut_mm
    if guard < 2.0:
        advice.append(
            (
                "warning",
                f"La garde entre Z_CUT et Z_TRAVEL n'est que de {guard:.1f} mm. "
                "Prévoyez 3 à 4 mm pour que la lame ne racle pas le papier "
                "entre deux contours.",
            )
        )
    if abs(cfg.offset_x_mm) < 0.05 and abs(cfg.offset_y_mm) < 0.05:
        advice.append(
            (
                "info",
                "Les offsets sont à zéro : c'est normal seulement si la lame "
                "est parfaitement alignée avec la buse. Sinon, faites le test "
                "de décalage avant la première planche.",
            )
        )
    if cfg.feed_cut > 1800:
        advice.append(
            (
                "warning",
                f"La vitesse de coupe ({cfg.feed_cut} mm/min) est élevée. "
                "Commencez plus doucement sur une chute, puis augmentez.",
            )
        )
    if abs(cfg.z_cut_mm - 14.2) < 0.01 and abs(cfg.z_travel_mm - 18.2) < 0.01:
        advice.append(
            (
                "info",
                "Les valeurs Z affichées sont celles d'exemple du projet. Elles "
                "dépendent entièrement de votre porte-lame : mesurez les vôtres "
                "avant la première découpe.",
            )
        )
    return advice
