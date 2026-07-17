import discord

RULES_DESCRIPTION = (
    "L'objectif de ce bot est d'écrire des anecdotes sur les autres joueurs du serveur, ou sur "
    "soi-même, puis de laisser tout le monde deviner à qui elles appartiennent.\n\n"
    "**Comment ça marche**\n"
    "- Il faut être inscrit pour participer (via les boutons d'inscription postés sur le "
    "serveur)\n"
    "- Envoie une anecdote en DM au bot, sur quelqu'un du serveur (ou sur toi-même !) avec "
    "`/anecdote submit`\n"
    "- Retrouve, modifie ou supprime tes anecdotes en attente avec `/anecdote list` — la commande "
    "affiche aussi leur % de chance d'être choisies au prochain tirage\n"
    "- À intervalle régulier, le bot publie une anecdote dans le channel dédié avec un QCM pour "
    "deviner à qui elle appartient. Le tirage est aléatoire mais pondéré : plus une anecdote "
    "attend, plus ses chances augmentent, et les auteurs publiés trop souvent sont "
    "temporairement désavantagés.\n"
    "- Après un délai de révélation, la réponse est dévoilée : +1 point pour chaque bonne réponse "
    "au QCM, et +1 point pour la personne qui a écrit l'anecdote.\n"
    "- Consulte le classement à tout moment avec `/leaderboard`\n"
    "- Retrouve la date de la prochaine publication et révélation avec `/next`\n\n"
    "**Commandes de base**\n"
    "- `/stats` — statistiques du jeu\n"
    "- `/rules` — revoir ces règles\n"
    "- `/help` — aide complète"
)


def build_rules_embed() -> discord.Embed:
    """Build the embed explaining the game rules and basic player commands."""
    return discord.Embed(
        title="📜 Règles du jeu",
        description=RULES_DESCRIPTION,
        color=discord.Color.blue(),
    )
