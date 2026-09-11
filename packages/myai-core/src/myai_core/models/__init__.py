"""Local model management and inference providers (spec §46, §69).

* ``catalog``  – curated, licensed models the app can offer to download
* ``download`` – resumable, integrity-verified downloader
* ``provider`` – the ``ModelProvider`` abstraction every backend implements
* ``llama_cpp_provider`` – the local backend (llama.cpp via llama-cpp-python)
* ``service``  – installs, activation, hardware fit
* ``runtime``  – process-wide loaded model + generation lock
"""
