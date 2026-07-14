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
    "- `/config reset` — réinitialiser la configuration\n\n"
    "**2. Inscrire les joueurs**\n"
    "- `/register-submitters` — inscrire ceux qui écrivent des anecdotes\n"
    "- `/register-targets` — inscrire ceux qui apparaissent dans le QCM\n\n"
    "**3. Collecter les anecdotes**\n"
    "- Les joueurs inscrits envoient leurs anecdotes en DM au bot\n\n"
    "**4. Démarrer le jeu**\n"
    "- `/start` — lancer les publications automatiques\n"
    "- `/stop` — mettre en pause\n"
    "- `/reset` — tout supprimer et recommencer\n\n"
)

USER_GUIDE = (
    "## 👤 Comment jouer\n\n"
    "**Soumettre une anecdote**\n"
    "Envoie un message privé au bot pour proposer une anecdote.\n\n"
    "**Voter**\n"
    "Quand une anecdote est publiée, réponds au QCM pour deviner "
    "à qui elle correspond.\n\n"
    "**Leaderboard**\n"
    "- `/leaderboard` — voir le classement actuel\n"
    "- +1 point par bonne réponse\n"
)


async def handle(interaction: discord.Interaction):
    """Show help guide adapted to user role."""
    is_admin = interaction.user.guild_permissions.administrator  # type: ignore[union-attr]

    if is_admin:
        content = ADMIN_GUIDE + USER_GUIDE
    else:
        content = USER_GUIDE

    embed = discord.Embed(
        title="AnecBot — Aide",
        description=content,
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
