"""Curated guide topics. Answers must stay true for the current build: say what exists,
what is planned, and which phase brings it. Keep each answer to a short paragraph."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GuideTopic:
    id: str
    title: str
    question: str
    """A canonical phrasing, shown as a suggestion."""
    keywords: tuple[str, ...]
    """Single words or short phrases. Phrase matches score double."""
    answer: str
    related: tuple[str, ...] = field(default_factory=tuple)


TOPICS: tuple[GuideTopic, ...] = (
    GuideTopic(
        id="training",
        title="Training",
        question="What is training?",
        keywords=("training", "train", "fine tune", "fine-tune", "finetune", "lora", "epochs"),
        answer=(
            "Training improves one skill using your own computer, and it is targeted: training "
            "Writing does not make your AI universally smarter. It does not change your model's "
            "weights \u2014 fine-tuning a quantised local model is not something this program can "
            "honestly do. Instead it searches for better instructions for that skill: short "
            "rules, rules your AI writes for itself after getting a practice task wrong, and "
            "worked examples. A change is kept only when it scores higher on practice tasks, "
            "and at the end the skill's benchmark decides whether the result is kept at all. "
            "If the benchmark does not improve, the old instructions stay and the run says so."
        ),
        related=("learning", "skills", "compute"),
    ),
    GuideTopic(
        id="learning",
        title="Learning a skill",
        question="What does /learn do?",
        keywords=("learn", "learning", "acquire", "teach", "skill package", "/learn"),
        answer=(
            "/learn <skill> shows what the skill package contains and what it will cost; "
            "'/learn <skill> start' installs the package (instructions your AI follows from "
            "then on) and runs the skill's benchmark with your local model. The level it "
            "scores becomes the skill's level. Conversation, Writing, Coding, Research and "
            "Science can be learned today; creative skills have no measurable benchmark yet "
            "and say so. Nothing is downloaded and the model is not retrained. Once a skill is "
            "learned, '/train <skill>' can practise it."
        ),
        related=("training", "skills", "levels"),
    ),
    GuideTopic(
        id="skills",
        title="Skills and the skill tree",
        question="What are skills?",
        keywords=("skills", "skill", "skill tree", "tree", "unlock", "specialization"),
        answer=(
            "Skills are the capabilities your AI can learn, grouped in a tree: Conversation "
            "first, then Writing, Coding, Research and Science, then creative skills like "
            "Images, Video and Music. Some skills require others. The Skills page shows what "
            "exists, what is locked and which phase makes each one learnable."
        ),
        related=("learning", "levels"),
    ),
    GuideTopic(
        id="levels",
        title="Levels and benchmarks",
        question="How do levels work?",
        keywords=("level", "levels", "xp", "benchmark", "benchmarks", "degree", "achievement"),
        answer=(
            "Every skill has a level from 1 to 100: the score of its most recent benchmark run "
            "with your local model. Time spent, downloads or wishes never raise a level; only a "
            "benchmark does, and /history lists every change. Your AI's headline level is the "
            "average of its three strongest skills. Degrees and achievements are computed from "
            "those measured levels and area scores."
        ),
        related=("skills", "training"),
    ),
    GuideTopic(
        id="erase",
        title="Taking your data out, or deleting it",
        question="How do I export or delete everything?",
        keywords=(
            "export",
            "backup",
            "delete",
            "erase",
            "remove",
            "wipe",
            "take out",
            "gdpr",
        ),
        answer=(
            "Security (or 'myai security export') writes an archive of everything this "
            "installation holds about you, with a manifest saying what is inside. Credentials "
            "are deliberately left out, and model files are listed rather than copied because "
            "they are large and downloadable again. 'Erase everything' shows the counts first, "
            "asks you to type a phrase, and then deletes the rows rather than marking them "
            "deleted. It cannot reach copies you made elsewhere, and deleted files are not "
            "overwritten, so use your system's secure-erase tool if that matters to you."
        ),
        related=("privacy", "account", "storage"),
    ),
    GuideTopic(
        id="privacy",
        title="Privacy",
        question="Where does my data go?",
        keywords=(
            "privacy",
            "private",
            "data",
            "upload",
            "cloud",
            "collect",
            "telemetry",
            "sell",
            "share",
            "leave",
        ),
        answer=(
            "Nowhere, unless you send it. Conversations, memories, files, training data and "
            "model weights stay on this computer. This build has no account, sync, telemetry "
            "or crash-reporting code. The Privacy Center lists exactly what touches the "
            "network: an internet reachability check and the model downloads you start."
        ),
        related=("offline", "account"),
    ),
    GuideTopic(
        id="offline",
        title="Working offline",
        question="Does it work offline?",
        keywords=("offline", "internet", "wifi", "airplane", "connection", "online"),
        answer=(
            "Yes. Once a model is installed, chat, memory and knowledge work with no internet "
            "at all. The status bar always distinguishes internet reachability from whether "
            "your AI is available. Downloads and future sync are the only features that need "
            "a connection."
        ),
        related=("privacy", "models"),
    ),
    GuideTopic(
        id="models",
        title="Local models",
        question="Which model does my AI use?",
        keywords=("model", "models", "download", "gguf", "llama", "qwen", "license", "licence"),
        answer=(
            "Your AI runs an open model file on your own hardware through llama.cpp. The "
            "Models page lists a small catalog with each licence shown before anything is "
            "downloaded; downloads resume and are checksum-verified. The suggested model "
            "depends on your hardware tier; larger models need more memory and are slower."
        ),
        related=("hardware", "offline"),
    ),
    GuideTopic(
        id="memory",
        title="Memory",
        question="What does my AI remember?",
        keywords=("memory", "memories", "remember", "forget", "recall"),
        answer=(
            "Only what you add on purpose. Memory is a list of facts you write down for your "
            'AI ("I prefer short answers"); it is included in every conversation and you can '
            "edit or delete any entry. Conversations are never turned into memories "
            "automatically."
        ),
        related=("knowledge", "privacy"),
    ),
    GuideTopic(
        id="knowledge",
        title="Knowledge",
        question="How do I give my AI documents?",
        keywords=("knowledge", "document", "documents", "pdf", "file", "files", "search", "cite"),
        answer=(
            "Add text, Markdown, code or PDF files under Knowledge. They are split into "
            "passages and indexed locally; when you chat, the most relevant passages are shown "
            "to the model and listed under the reply so you can see what it used. Retrieval "
            "is keyword-based in this build."
        ),
        related=("memory",),
    ),
    GuideTopic(
        id="hardware",
        title="Hardware tiers",
        question="What does my hardware tier mean?",
        keywords=("hardware", "tier", "gpu", "vram", "ram", "cpu", "slow", "fast", "requirements"),
        answer=(
            "The tier (Entry to Workstation) is an estimate from your specifications, mainly "
            "GPU memory and RAM. It only orders recommendations; it is not a guarantee. The "
            "Hardware page can run a short benchmark that measures memory bandwidth and, once "
            "a model is installed, real tokens per second."
        ),
        related=("compute", "models"),
    ),
    GuideTopic(
        id="compute",
        title="Compute settings",
        question="What do the compute settings do?",
        keywords=(
            "compute",
            "balanced",
            "maximum",
            "hot",
            "hotter",
            "fan",
            "utilization",
            "thread",
        ),
        answer=(
            "Low, Balanced, High and Maximum decide how much of your CPU and GPU MyAI may use "
            "(25% to 100%). Higher settings may make your computer slower and hotter. Advanced "
            "mode exposes exact limits; hardware safety controls are never bypassed."
        ),
        related=("hardware", "training"),
    ),
    GuideTopic(
        id="storage",
        title="Storage",
        question="Where are my files stored?",
        keywords=(
            "storage",
            "disk",
            "folder",
            "space",
            "ssd",
            "external drive",
            "drive",
            "cleanup",
        ),
        answer=(
            "Small app data (the database and the local API token) lives in your user profile. "
            "Everything large - models, skills, training data, checkpoints, knowledge, "
            "generated media - lives in the MyAI storage folder you chose, which can be on an "
            "external SSD. The Storage page shows usage per category and offers a cleanup of "
            "leftovers; it warns before touching training resources."
        ),
        related=("privacy",),
    ),
    GuideTopic(
        id="account",
        title="Accounts and devices",
        question="Do I need an account?",
        keywords=(
            "account",
            "sign in",
            "login",
            "log in",
            "subscription",
            "phone",
            "mobile",
            "pair",
            "sync",
        ),
        answer=(
            "There is no account in this build: no account server, nothing to sign in to, and "
            "no code path that would send anything to one. An account is planned as the way to "
            "download installers and to pair phones and other computers; it will never receive "
            "your private data. What exists today is local: each program you pair gets its own "
            "credential you can revoke on its own, and the service only listens on 127.0.0.1, "
            "so nothing on your network can reach it."
        ),
        related=("privacy", "offline", "erase"),
    ),
    GuideTopic(
        id="commands",
        title="Commands",
        question="Which commands can I use?",
        keywords=("command", "commands", "slash", "/help", "console", "type"),
        answer=(
            "Type /help in the Console or in Chat for the list: /status, /hardware, /skills, "
            "/memory, /settings work now; /learn, /train, /pause, /resume, /stop, /history and "
            '/projects explain which phase brings them. Plain sentences like "teach yourself '
            'video" are mapped to a command and the mapping is shown.'
        ),
        related=("learning", "training"),
    ),
    GuideTopic(
        id="name",
        title="Your AI's identity",
        question="Can I rename my AI?",
        keywords=("name", "rename", "personality", "identity", "owner", "profile"),
        answer=(
            "Yes. The name, personality and communication style live on the My AI page and "
            "can be changed at any time. Personality shapes how the model is prompted; it is "
            "separate from training and never retrains anything."
        ),
        related=("memory",),
    ),
)

BY_ID: dict[str, GuideTopic] = {t.id: t for t in TOPICS}
