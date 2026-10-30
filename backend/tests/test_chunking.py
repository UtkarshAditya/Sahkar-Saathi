"""Unit tests for corpus text cleaning and chunking (role B)."""

from apps.knowledge.management.commands.ingest_corpus import (
    chunk_text,
    clean_page_text,
    is_mostly_glyph_garbage,
    split_sentences,
)


def test_clean_page_text_strips_cid_artifacts():
    raw = "The society shall (cid:0) maintain (cid:123) books of accounts."
    cleaned = clean_page_text(raw)
    assert "(cid:" not in cleaned
    assert "The society shall  maintain  books of accounts." in cleaned


def test_clean_page_text_strips_fontawesome_glyphs():
    raw = (
        "Social media links:\n\uf09a\n\uf167\n\uf099\n\uf16d\n\uf0e1\n"
        "Legitimate paragraph text here."
    )
    cleaned = clean_page_text(raw)
    assert "\uf09a" not in cleaned
    assert "Legitimate paragraph text here." in cleaned


def test_clean_page_text_strips_crcs_boilerplate():
    raw = (
        "Go to Main Content Sitemap Contact us A+ A A- A A English\n"
        "Government of India\n"
        "Registration of New MSCS\n"
        "Ministry of Cooperation CR Login Reg\n"
        "Central Registrar of Cooperative Societies Login\n"
        "Home / FAQs\n"
        "Every multi-state cooperative society shall file annual returns within six months.\n"
        "Last updated: 13 Oct 2026\n"
        "Home State Registrars List of MSCS Banks Ministry of Cooperation website Contact us\n"
        "Terms & Conditions Copyright Policy Privacy Policy Hyperlinking Policy Help "
        "Disclaimer Web Information Manager(WIM)\n"
        "© Content Owned by Ministry of Cooperation, Government of India. All Rights Reserved ."
    )
    cleaned = clean_page_text(raw)
    assert "Every multi-state cooperative society shall file annual returns" in cleaned
    assert "Go to Main Content" not in cleaned
    assert "Government of India" not in cleaned
    assert "Terms & Conditions" not in cleaned
    assert "Content Owned by Ministry of Cooperation" not in cleaned


def test_clean_page_text_strips_tn_rcs_footer():
    raw = """Cooperative banks shall adhere to RBI guidelines on asset classification.
OFFICE OF THE REGISTRAR OF COOPERATIVE SOCIETIES USEFUL LINKS
NVN Natarajan Maligai
No.170, Periyar E.V.R. High Road
Kilpauk Chennai - 600 010
Phone No.: 044-28364855
Paniyaalar Naal VILUTHUGAL
Email id: rcs.tn@nic.in
VERGAL Contact Us
Copyright © 2024, All Right Reserved REGISTRAR OF COOPERATIVE SOCIETIES
designed by Trophy systems"""
    cleaned = clean_page_text(raw)
    assert "Cooperative banks shall adhere to RBI guidelines" in cleaned
    assert "OFFICE OF THE REGISTRAR" not in cleaned
    assert "designed by Trophy systems" not in cleaned
    assert "Copyright © 2024" not in cleaned


def test_maintenance_is_never_stripped():
    raw = """Maintenance of records is mandatory under Section 4 of the TN RTI Manual 2015.
Routine maintenance and repair charges of office equipment shall be documented."""
    cleaned = clean_page_text(raw)
    assert "Maintenance of records is mandatory" in cleaned
    assert "Routine maintenance and repair charges" in cleaned

    chunks = chunk_text(raw, max_chars=900, min_chars=50, tail_merge_chars=150)
    assert any("Maintenance of records" in c for c in chunks)
    assert any("Routine maintenance" in c for c in chunks)


def test_is_mostly_glyph_garbage_detection():
    normal_text = "Section 26 of the Multi-State Cooperative Societies Act provides for audit."
    assert not is_mostly_glyph_garbage(normal_text)

    # Isolated cid artifact is not mostly garbage
    slightly_flawed = "Section 26 (cid:1) of the Act."
    assert not is_mostly_glyph_garbage(slightly_flawed)

    # Dominated by (cid:NNN)
    garbage = " ".join(f"(cid:{i})" for i in range(50))
    assert is_mostly_glyph_garbage(garbage)


def test_split_sentences_preserves_abbreviations():
    text = (
        "The society filed G.O. (2D) No.108 on 15.08.2024. "
        "It was registered u/s 12 of the Act, e.g. for agricultural credit. "
        "The board meeting followed thereafter."
    )
    units = split_sentences(text)
    # Ensure "G.O. (2D) No.108" and "e.g." do not split the sentence prematurely
    assert len(units) == 3
    assert units[0][0].startswith("The society filed G.O. (2D) No.108")
    assert "e.g. for agricultural credit" in units[1][0]


def test_split_sentences_detects_section_headings():
    text = """32. General meetings of the society.
The general body of a multi-state cooperative society shall meet once a year.
CHAPTER IV: Management and Direction
The board of directors shall superintend the affairs."""
    units = split_sentences(text)
    headings = [u[0] for u in units if u[1]]
    assert "32. General meetings of the society." in headings
    assert "CHAPTER IV: Management and Direction" in headings


def test_chunk_never_splits_mid_word():
    text = "Wordone wordtwo wordthree wordfour wordfive wordsix wordseven. " * 30
    chunks = chunk_text(text, max_chars=300, min_chars=80, tail_merge_chars=100)
    allowed_words = {
        "Wordone",
        "wordtwo",
        "wordthree",
        "wordfour",
        "wordfive",
        "wordsix",
        "wordseven.",
    }
    for chunk in chunks:
        # Each chunk must start and end with complete words (not chopped characters)
        words = chunk.split()
        for w in words:
            assert w in allowed_words


def test_chunks_enforce_min_chars():
    short_text = "This is a tiny note."  # 20 chars < min_chars (80)
    chunks = chunk_text(short_text, max_chars=900, min_chars=80, tail_merge_chars=150)
    assert chunks == []


def test_tail_merge_incorporates_short_trailing_text():
    # Sentence 1: ~400 chars, Sentence 2: ~120 chars (<= tail_merge_chars 150)
    sent1 = "The primary agricultural credit society serves farmers with short-term credit. " * 5
    sent2 = "All members must hold shares in the society to qualify."
    text = sent1 + "\n" + sent2

    chunks = chunk_text(text, max_chars=500, min_chars=80, tail_merge_chars=150)
    # The second sentence should be merged into the first chunk because it is <= 150 chars
    assert len(chunks) == 1
    assert "All members must hold shares" in chunks[0]


def test_sentence_overlap_between_chunks():
    s1 = "First sentence establishes the general powers and duties of the cooperative committee."
    s2 = "Second sentence details the financial reserves required to be kept in approved banks."
    s3 = "Third sentence describes the procedure for arbitration in disputes between members."
    s4 = "Fourth sentence specifies penal provisions for non-compliance with statutory audit."
    text = f"{s1} {s2} {s3} {s4}"

    # Use a small max_chars (180) to force multiple chunks
    chunks = chunk_text(text, max_chars=180, min_chars=50, tail_merge_chars=40)
    assert len(chunks) >= 2
    # Verify consecutive chunks share overlap sentences
    overlap_found = False
    for i in range(len(chunks) - 1):
        c1_words = set(chunks[i].split())
        c2_words = set(chunks[i + 1].split())
        if len(c1_words.intersection(c2_words)) >= 4:
            overlap_found = True
            break
    assert overlap_found
