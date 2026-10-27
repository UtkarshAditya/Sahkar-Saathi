import asyncio
from pathlib import Path

from .whisper_provider import WhisperSpeechProvider


async def run_evaluation():
    provider = WhisperSpeechProvider()

    # Define your test samples: (file_path, ground_truth_text, language_code)
    test_cases = [
        ("path/to/english_sample.m4a", "What is the premium share for PMFBY?", "en"),
        ("path/to/tamil_sample.m4a", "பிரதான் மந்திரி फसल बीमा योजना", "ta"),
    ]

    print("--- Starting Whisper Evaluation Run ---")
    for file_path, gt_text, lang in test_cases:
        path = Path(file_path)
        if not path.exists():
            print(f"Skipping {file_path} (File not found)")
            continue

        audio_bytes = path.read_bytes()
        result = await provider.transcribe(
            audio_bytes, content_type="audio/m4a", language_hint=lang, use_vocabulary_hint=True
        )

        print(
            f"\nFile: {path.name} | Language: {result.language} | Confidence: {result.confidence:.2f}"
        )
        print(f"Ground Truth: {gt_text}")
        print(f"Transcript:   {result.text}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
