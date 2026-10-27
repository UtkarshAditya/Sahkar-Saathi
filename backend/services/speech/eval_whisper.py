import asyncio
from pathlib import Path


async def run_evals(test_cases, provider):
    for file_path, gt_text, lang in test_cases:
        path = Path(file_path)
        if not await asyncio.to_thread(path.exists):
            print(f"Skipping {file_path} (File not found)")
            continue

        audio_bytes = await asyncio.to_thread(path.read_bytes)
        result = await provider.transcribe(
            audio_bytes, content_type="audio/m4a", language_hint=lang, use_vocabulary_hint=True
        )
        print(
            f"\nFile: {path.name} | Language: {result.language} "
            f"| Confidence: {result.confidence:.2f}"
        )
        print(f"Ground Truth: {gt_text}")
