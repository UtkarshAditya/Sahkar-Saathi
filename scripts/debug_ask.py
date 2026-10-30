import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(name)s: %(message)s")
for noisy in (
    "httpx",
    "httpx2",
    "httpcore",
    "sentence_transformers",
    "huggingface_hub",
    "urllib3",
    "filelock",
    "asyncio",
):
    logging.getLogger(noisy).setLevel(logging.WARNING)

import services.answer as A  # noqa: E402
from config.services import get_answer_service, get_retriever  # noqa: E402

RELAX = False  # change to True to try the relaxed prompt, without a rebuild

if RELAX:
    A.SYSTEM_PROMPT = """You answer questions about cooperative societies and farmer schemes in India.
Rules:
1. Use ONLY facts that appear in the numbered passages provided. Never use outside knowledge
   and never guess.
2. Every claim must come from a passage that you cite. List the numbers of the passages you
   used in "cited_ids".
3. A passage that states a right, duty or procedure that applies to members, or to cooperative
   societies in general, DOES answer a question about that right, duty or procedure. Ignore only
   passages about a clearly different matter. For example, a rule about refusing to register a
   new society says nothing about a member's deposit in an existing society.
4. If no passage answers the question, set "status" to "declined", leave "cited_ids" empty and
   say you could not find it. A decline is better than a wrong answer.
5. Copy numbers, dates, time limits and deadlines exactly as written in the passages. Mention a
   section or rule number only if it appears in the passage you cite.
6. Do not repeat the question. Keep the answer short: at most 3 sentences, or a short list.
7. Give legal information only. Never predict the outcome of a dispute or say what someone
   will win.
8. Write the answer in the language of the question. If you are not sure of the language,
   write in English.
Reply with JSON only, in exactly this shape:
{"status": "answered" or "declined", "answer_text": "...", "cited_ids": [1, 2]}"""
QUESTIONS = [
    "Where can a member of a multi-State cooperative society complain about a deposit that is not returned?",
    "How do I file a request for information under the Right to Information Act with the Tamil Nadu Cooperation Department?",
    "What is the minimum number of members needed to register a primary cooperative society in Tamil Nadu?",
]
svc = get_answer_service()
# try 8 instead of 4


async def main():
    for q in QUESTIONS:
        print("\n==========", q)
        passages = await get_retriever().search(q, state="TN", language="en", top_k=4)
        for p in passages:
            print(
                f"  {p.score:.3f} | {p.document_id} | p.{p.page} | "
                f"{p.text[:200].replace(chr(10), ' ')}"
            )
        a = await get_answer_service().ask(q, language="en", state="TN")
        print("RESULT:", a.status, a.top_score, "|", (a.text or "")[:400])
        for c in a.citations:
            print("   CITED:", c.document_id, "p.", c.page, "|", c.text[:120].replace(chr(10), " "))


asyncio.run(main())
