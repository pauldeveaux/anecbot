import logging

import discord

GENERIC_ERROR_MESSAGE = "❌ Une erreur est survenue, réessaie plus tard."


async def notify_unexpected_error(
    interaction: discord.Interaction, error: Exception, logger: logging.Logger
) -> None:
    """Log an unexpected interactive-component error and notify the user via an ephemeral message."""
    logger.exception("Unexpected error in interactive component", exc_info=error)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(GENERIC_ERROR_MESSAGE, ephemeral=True)
        else:
            await interaction.response.send_message(
                GENERIC_ERROR_MESSAGE, ephemeral=True
            )
    except discord.HTTPException:
        logger.debug("Could not notify user %s of error", interaction.user.id)
