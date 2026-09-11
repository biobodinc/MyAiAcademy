"""The built-in onboarding guide (spec §66).

A deterministic, curated question-answerer about MyAI Academy itself. It is *not* the
user's AI model and every surface that shows an answer says so. It exists so a brand-new
user can ask "what is training?" before any model is installed, and so the console can
answer product questions without pretending to be a chatbot.
"""

from myai_core.guide.service import GuideAnswer, GuideTopicRead, ask, topics

__all__ = ["GuideAnswer", "GuideTopicRead", "ask", "topics"]
