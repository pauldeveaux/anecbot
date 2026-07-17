import discord

ADMIN_GUIDE = (
    "## 📋 Guide administrateur\n\n"
    "**1. Configurer le bot**\n"
    "- `/config channel` — choisir le channel du quiz\n"
    "- `/config interval` — intervalle entre les publications\n"
    "- `/config publish-time` — heure de publication\n"
    "- `/config days-off` — jours sans publication\n"
    "- `/config reveal-interval` — délai avant la révélation\n"
    "- `/config reveal-time` — heure de révélation\n"
    "- `/config timezone` — fuseau horaire du serveur (ex: Europe/Paris)\n"
    "- `/config leaderboard-reset-frequency` — fréquence de reset du leaderboard "
    "(daily/weekly/monthly/yearly)\n"
    "- `/config leaderboard-every` — tous les combien (ex: tous les 2 mois)\n"
    "- `/config leaderboard-reset-day` — jour de reset (selon la fréquence)\n"
    "- `/config leaderboard-reset-time` — heure de reset du leaderboard\n"
    "- `/config daily-limit` — limite quotidienne de soumissions par personne\n"
    "- `/config show` — afficher la configuration actuelle\n"
    "- `/config reset` — réinitialiser la configuration\n\n"
    "**2. Gérer les joueurs**\n"
    "- `/register-submitters [role]` — ouvrir les inscriptions pour écrire des anecdotes\n"
    "- `/register-targets [role]` — ouvrir les inscriptions pour être cible\n"
    "- `/register <user> <role>` — inscrire un joueur directement\n"
    "- `/unregister <user> [role]` — désinscrire un joueur\n"
    "- `/alias <user> <nom>` — définir un alias d'affichage\n"
    "- `/suspend <user>` / `/unsuspend <user>` — mettre en pause (exclu des publications et du QCM)\n"
    "- `/ban <user> [role]` / `/unban <user> [role]` — bannir / débannir\n"
    "- `/players [filtre]` — lister les joueurs (rédacteurs/cibles/bannis)\n\n"
    "**3. Collecter les anecdotes**\n"
    "- Les joueurs inscrits utilisent `/anecdote submit` en DM au bot\n\n"
    "**4. Démarrer le jeu**\n"
    "- `/start` — lancer les publications automatiques\n"
    "- `/stop` — mettre en pause\n"
    "- `/reset` — tout supprimer et recommencer\n\n"
    "**5. Règles**\n"
    "- `/publish-rules` — publier les règles du jeu dans le channel configuré\n\n"
)

DM_GUIDE = (
    "## 👤 Comment jouer\n\n"
    "**Soumettre une anecdote**\n"
    "- `/anecdote submit` — envoyer une anecdote\n"
    "- `/anecdote list` — voir, modifier ou supprimer tes anecdotes en attente\n\n"
    "**Inscription**\n"
    "- `/leave [role]` — se désinscrire d'un rôle ou complètement\n\n"
    "Les commandes suivantes sont disponibles **sur le serveur** :\n"
    "- `/stats` — statistiques du jeu\n"
    "- `/next` — prochains événements\n"
    "- `/leaderboard` — classement\n\n"
    "**Règles**\n"
    "- `/rules` — revoir les règles du jeu\n"
)

USER_GUIDE = (
    "## 👤 Comment jouer\n\n"
    "**Soumettre une anecdote**\n"
    "- `/anecdote submit` — envoyer une anecdote (en DM)\n"
    "- `/anecdote list` — voir, modifier ou supprimer tes anecdotes en attente (en DM)\n\n"
    "**Voter**\n"
    "Quand une anecdote est publiée, réponds au QCM pour deviner "
    "à qui elle correspond.\n\n"
    "**Inscription**\n"
    "- `/leave <role>` — se désinscrire d'un rôle ou complètement\n\n"
    "**Statistiques**\n"
    "- `/stats` — voir les statistiques du jeu\n"
    "- `/next` — voir les prochains événements prévus\n\n"
    "**Leaderboard**\n"
    "- `/leaderboard` — voir le classement actuel\n"
    "- +1 point par bonne réponse\n\n"
    "**Règles**\n"
    "- `/rules` — revoir les règles du jeu\n"
)


async def handle(interaction: discord.Interaction):
    """Show help guide adapted to context and role."""
    if interaction.guild is None:
        content = DM_GUIDE
    elif interaction.user.guild_permissions.administrator:  # type: ignore[union-attr]
        content = ADMIN_GUIDE + USER_GUIDE
    else:
        content = USER_GUIDE

    embed = discord.Embed(
        title="AnecBot — Aide",
        description=content,
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
