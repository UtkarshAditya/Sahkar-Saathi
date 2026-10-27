import asyncio
from pathlib import Path

from .whisper_provider import whisper_provider


async def evaluate_recording(file_path: str, ground_truth: str, language: str):
    path = Path(file_path)
    if not await asyncio.to_thread(path.exists):
        print(f"Error: Audio file not found at {file_path}")
        return

    audio_bytes = await asyncio.to_thread(path.read_bytes)
    print(f"\n[Evaluating] File: {path.name} | Language: {language}")

    try:
        transcript = await whisper_provider.transcribe(audio_bytes, language=language)
        print(f"-> Ground Truth: {ground_truth}")
        print(f"-> Transcript:   {transcript}")

        # Simple word error metric check
        gt_words = set(ground_truth.lower().split())
        tr_words = set(transcript.lower().split())
        overlap = len(gt_words.intersection(tr_words))
        score = (overlap / len(gt_words)) * 100 if gt_words else 0
        print(f"-> Keyword Overlap Match Score: {score:.1f}%")
    except Exception as e:
        print(f"-> Error during transcription: {e}")


if __name__ == "__main__":
    # Example usage execution test
    print("Running Whisper Evaluation Suite...")
    # Add your test samples here
    # asyncio.run(evaluate_recording("sample_en.m4a", "What is the premium share for PMFBY?", "en"))
    # asyncio.run(evaluate_recording("sample_ta.m4a", "பிரதான் மந்திரி फसल बीमा योजना", "ta"))
