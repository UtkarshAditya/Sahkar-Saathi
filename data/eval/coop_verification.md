# Cooperative verification of `tamil_questions.csv` (T16 to T19)

Evidence for a person to read. **Nothing here changes a `status` in the CSV.** These four rows
have no expected answer yet; a person decides what to write, from the provisions below.

## Sources searched

| File in `data/raw/` | What it is | Searched |
|---|---|---|
| `TN-COOP-ACT-1983_en.pdf` | Tamil Nadu Co-operative Societies Act, 1983, corrected up to 23.09.2022 (146 pages) | in full |
| `TN-COOP-RULES-1988_en.pdf` | Tamil Nadu Co-operative Societies Rules, 1988, corrected up to 23.09.2022 (318 pages) | in full |
| `CEN-MSCS-ACT-2023_en.pdf` | Multi-State Co-operative Societies (Amendment) Act, 2023 (23 pages) | in full |
| `CEN-MSCS-AMEND-RULES-2023_en.pdf`, `CEN-MSCS-NOTIF-2023_en.pdf` | G.S.R. 591(E) and S.O. 3493(E) | in full (short; no hits) |
| `TN-CITIZEN-CHARTER-2023_en.pdf`, `TN-POLICY-NOTE-2023_en.pdf`, `TN-RTI-MANUAL-2015_en.pdf`, `CEN-PIB-INITIATIVES-2026_en.pdf`, `CEN-CEA-INFO-NOTE-2026-07_en.pdf` | department and ministry documents | searched for the four topics; **no hits** |

**Not available in the repo** (the CSV lists them, the files are missing): the consolidated
Multi-State Act 2002 (`CEN-MSCS-ACT-2002`), the Multi-State Rules, the central model by-laws
(`CEN-PACS-MODEL-BYLAWS`) and the Tamil Nadu PACCS model by-laws (`TN-PACCS-BYLAWS-2022`). A
society's own by-laws are never in the corpus. The answers below can therefore only cover the
Tamil Nadu Act and Rules and the 2023 amendments to the Multi-State Act.

**Method.** Text extracted with poppler `pdftotext -raw` (`pdfplumber` is not installed here and
was not downloaded); quotes join line breaks into single spaces and are otherwise as extracted.
Footnote markers such as `1[` and `2[` that the Act's amendments leave in the text, and the
Act's `__` after a heading, are omitted. `PDF p.N` is the PDF page; the printed page is shown
where it was read from the page. For the Tamil Nadu Act and Rules, printed = PDF − 14.

Verdicts: **ANSWERED** (a provision directly answers the question), **NEARBY** (related
provisions exist but none answers it directly), **NOT IN CORPUS**. A NEARBY provision is never an
answer.

| id | Tamil Nadu society | Multi-State society |
|---|---|---|
| T16 deposit | **NEARBY** | **ANSWERED** (s.85A(1)) |
| T17 accounts and audit report | **ANSWERED** (s.27, rule 102(9)) | NEARBY (s.106) |
| T18 membership refused | **NEARBY** | NOT IN CORPUS |
| T19 improper election | **ANSWERED** (s.90, s.33-A) | NEARBY (s.45) |

---

## T16, a society does not return a member's deposit

- **Question:** My cooperative society has not returned my deposit. What can I do?
- **Earlier finding (to confirm or correct):** no ingested provision answers the deposit question.

### Tamil Nadu society: NEARBY

A fresh search of the Act and Rules for *deposit* (every hit checked, and the *share* provisions) found
**no provision that obliges a society to return a member's deposit or says what a depositor can do
if it does not.**

- **Share capital, not deposits.** Section 29, TN Act, PDF p.37 (printed p.23):
  > 29. Restriction on withdrawal of share or interest by members of registered societies. Except in the case of death or expulsion or removal of the member or the permanent shifting of his residence outside the area of operation of the registered society, the share or interest in the capital of such member shall not be refunded unless- (a) such member has held the share or interest for not less than two years; and (b) such refund is in accordance with the by-laws of the registered society;

  Section 30(2) and (3), same page, cover payment to the nominee, heir or legal representative of a
  deceased member: "(3) A registered society may pay all other moneys due to the deceased member
  from the society to such nominee, heir or legal representative, as the case may be." These are
  about a member's **share or interest**, and death.
- **The society's charge over deposits.** Section 42, PDF p.57 (printed p.43):
  > 42. Charge and set off in respect of shares or interest of member. A registered society shall have a charge upon the share or interest in the capital and on the deposits of a member or past or deceased member and upon any dividend, bonus or profits payable to a member or a past member or the estate of a deceased member in respect of any debt due from such member or past member or the estate of such deceased member to the society, and may set off any sum credited or payable to a member or past member or deceased member or the estate of a deceased member in or towards payment of any such debt.

  This lets a society set a debt off against a deposit; it says nothing about repayment on demand.
- **Receiving deposits.** Section 67, PDF p.66: "67. Restrictions on borrowings. A registered
  society shall receive deposits and loans only to such extent and subject to such conditions as
  may be prescribed or specified in the by-laws." The conditions are in the Rules and the by-laws.
- **Liquidity duty.** Rule 80(1), TN Rules, PDF p.113: a society accepting deposits "shall maintain
  fluid resources", which includes "(iv) the entire amount of matured deposits (fixed, recurring
  and provident fund deposits) pending payment". It is a prudential rule for the society, not a
  member's remedy.
- **The only general route: the dispute section.** Section 90(1), PDF p.89 (printed p.75):
  > 90. Disputes. (1) If any dispute touching the constitution of the board or the management or the business of a registered society (other than a dispute regarding disciplinary action [...] against a paid servant of the society) arises (a) among members, past members and persons claiming through members, past members and deceased members; or (b) between a member, past member or person claiming through a member, past member or deceased member and the society, its board or any officer, agent or servant of the society, or [...] such dispute shall be referred to the Registrar for decision.

  A deposit claim could be argued to be a dispute "touching ... the business" of the society, but
  **the section does not mention deposits**. That is an interpretation, not a provision that
  answers the question. The limitation period for a referral is in s.90(9)(a)(ii): "six years from
  the date on which the act or omission with reference to which the dispute arose, took place"
  (PDF p.91, printed p.77).
- **Confirmed:** the earlier finding holds **for a Tamil Nadu society.**

### Multi-State society: ANSWERED

Section 85A(1), inserted by the 2023 Amendment Act (section 31 of that Act), PDF p.14:
> 85A. (1) The Central Government shall appoint, one or more Co-operative Ombudsman with territorial jurisdiction for inquiring into the complaints made by any member of the multi-State co-operative societies regarding their deposits, equitable benefits of society's functioning or any other issue affecting the individual rights of the concerned member, in such manner, as may be prescribed.
>
> (2) The Co-operative Ombudsman shall, on receipt of a complaint, complete the process of inquiry and adjudicate within a period of three months from the date of receipt of the complaint and may issue necessary directions to the society during the course of inquiry and the society shall be bound to comply with the same within a period of one month from the date of issuance of such directions.

- **Correction to the earlier finding:** the earlier note said the Ombudsman route is for multi-State
  societies only. That is right, and it is stronger than "no provision": for a **multi-State**
  society a provision **does** name deposits. Which route applies depends on whether the society is
  registered under the Tamil Nadu Act or the Multi-State Act, which the question does not say.
- The manner of filing a complaint is "as may be prescribed"; the rules for it are not in the corpus
  (`CEN-MSCS-AMEND-RULES-2023_en.pdf` has only 5 short pages and no such rules in its text).

## T17, a member's right to see accounts and the audit report

- **Question:** Can a member see the society's accounts and audit report?

### Tamil Nadu society: ANSWERED, within limits

- **Accounts.** Section 27, TN Act, PDF p.36 (printed p.22):
  > 27. Inspection of accounts by member. Any member of a registered society may, at any time during office hours and on payment of such fee as may be prescribed, by himself or by an agent who is a member specially authorized by him in writing, inspect and shall have access to the books, information and the accounts of the society in so far as they relate to his transactions with it.
- **The fee.** Rule 40, TN Rules, PDF p.59 (printed p.45):
  > 40. Fees for inspection of accounts by members. The fee payable under section 27 for inspection of accounts shall be - (i) five rupees for any one co-operative year to which the accounts to be inspected relate; (ii) three rupees for every such additional co-operative year; and (iii) twenty five rupees for any one member at any one such inspection: Provided that the by-laws may specify any fee not exceeding the rate specified in this rule.
- **The audit report.** Rule 102(9), TN Rules, PDF p.133 (printed p.119):
  > (9) The society shall publish (i) the audit certificate; (ii) the profit and loss account; and (iii) the balance sheet; in the manner specified by the Registrar (Audit) and shall also keep them open for inspection by any member of the society. The summary of the audit memorandum shall also be read out at the general meeting of the society.
- **What this says, and does not say.** A member may inspect the accounts **only "in so far as they
  relate to his transactions"** (s.27), and the society must keep the **audit certificate, profit
  and loss account and balance sheet** open for inspection by any member (rule 102(9)). Only a
  **summary** of the audit memorandum is read out at the general meeting. The Act and Rules found
  contain **no right for a member to see the full audit memorandum or the society's books beyond
  his own transactions.**

### Multi-State society: NEARBY

Section 106(1) to (3), inserted by the 2023 Amendment Act (section 39), PDF p.17:
> 106. (1) Every multi-State co-operative society shall appoint a Co-operative Information Officer to provide the information relating to affairs and management of the society to the members of the society and such information shall be confined to the information falling under the disclosure norms specified by the society in its bye-laws. (2) Any member of multi-State co-operative society shall make an application, accompanying such fee as may be prescribed, to get information specified in sub-section (1). (3) The Co-operative Information Officer shall, within thirty days from the date of receipt of application, either provide the information or reject the application specifying the reason to do so.

Whether accounts and the audit report fall under the disclosure norms depends on the society's
own by-laws (not in the corpus). Section 106(4) lets a member whose application was rejected
appeal to the Co-operative Ombudsman within one month.

## T18, membership refused: where to appeal

- **Question:** Whom can I appeal to if my membership is refused?

### Tamil Nadu society: NEARBY

**No provision found that gives an applicant an appeal against a refusal of admission.**

- The refusal itself, section 21(2)(i), PDF p.31 to 32 (printed p.17 to 18):
  > (2) (i) In the case of every registered society, every individual eligible for admission as a member of any such society under the provisions of this Act, the rules and the by-laws of the society shall, on application made in such form and in such manner as may be prescribed, be admitted by the board or by the general body, where there is no board as a member of the society with effect from the date of receipt of such application in the office of such society: Provided that the board or the general body, as the case may be, may, for good and sufficient reasons to be recorded in the minutes of the meeting at which the application for admission is considered, refuse admission to any individual and the decision of the board or the general body, as the case may be, shall be communicated to the individual: Provided further that if the decision of the board or the general body, as the case may be, on the application is not communicated to the individual within a period of sixty days from the date of receipt of the application in the office of the society, the individual shall be deemed to have been admitted as a member of such society, on the sixtieth day after the date of receipt of the application in the office of the society.
- **Nearby, but not an appeal against refusal:**
  - Section 23(4), PDF p.34: "Any question as to whether an applicant for admission as a member of a society is, or a member of a registered society was, or has become, subject to any of the disqualifications mentioned in this section, shall be decided by the Registrar." This covers a disqualification **question**, not a refusal for other reasons.
  - Section 24(2) and (4), PDF p.34 to 35: a **member** who "is refused any services" may "apply to the Registrar for redress", and the Registrar may direct the board "to render the service" if the refusal is "unreasonable, improper or discriminatory". This is about **services to a member**, not admission.
  - Section 90(1)(b) lets a **member** or past member refer a dispute with the society to the Registrar. An applicant who has been refused is not a member, so the text does not clearly cover them.
  - The schedule of fees for petitions and applications in the Rules (PDF p.302) lists "(d) Application for removal of a member under sub-clause (ii) of clause (a) of sub-section (2) of section 21", "(e) Application for decision regarding disqualification of a member under sub-section (4) of section 23" and "(f) Application against refusal of services under sub-section (2) of section 24", but **no application against a refusal of admission**.
- A reader should not state an appeal route for refused admission from these provisions.

### Multi-State society: NOT IN CORPUS

The provisions on admission of members are in the consolidated Act of 2002, which is not in the repo.
The 2023 Amendment Act amends section 28 (PDF p.3, the words "of all dues to the multi-State
co-operative society including the payment in respect of membership") but contains no appeal
against refusal of membership. Its only "rejected application" appeal is the one for **information** in s.106(4).

### Grievance guide (read, not edited)

- `backend/services/grievance.py` has a category **"Membership refused or removed"**
  (`membership`) and a category for being refused accounts, audit reports or minutes. But
  `FORUMS_BY_CATEGORY` holds only `"crop-insurance"`, and the file's own comment reads
  "forums.yaml has routes for crop insurance only; the cooperative categories have none yet".
- `backend/services/data/forums.yaml` lists three forums, all for crop insurance
  (`krph_helpline`, `ncip_portal_grievance`, `state_agriculture_department`).
- **So there is no forum for membership refusal.** The guide detects the category and says it has
  no route for it.

## T19, a board election not held properly

- **Question:** What can I do if the society's board election was not held properly?

### Tamil Nadu society: ANSWERED

- **Who runs elections.** Section 33-A(1), TN Act, PDF p.45 to 46 (printed p.31 to 32):
  > 33-A. Tamil Nadu State Co-operative Societies Election Commission. (1) The superintendence, direction and control of the preparation of electoral rolls for, and the conduct of, all elections to a co-operative society shall vest in the Tamil Nadu State Co-operative Societies Election Commission consisting of a Tamil Nadu State Co-operative Societies Election Commissioner.
- **The remedy: refer the dispute to the Registrar.** Section 90(1), PDF p.89 (printed p.75), quoted in T16, covers "any dispute touching the constitution of the board" among members or between a member and the society. Its proviso, same page:
  > Provided that no dispute relating to, or in connections with, any election shall be referred under this sub - section till the date of the declaration of the result of such election.
- **The time limit.** Section 90(9)(a)(iii), PDF p.91 (printed p.77):
  > (iii) when the dispute is in respect of, or in connection with, any election, the period of limitation shall be two months from the date of declaration of the result of the election.

  and 90(9)(b): "the Registrar may admit a dispute after the expiry of the period of limitation if the applicant satisfies the Registrar that he had sufficient cause for not referring the dispute within such period".
- **What this says:** an election dispute is referred **to the Registrar**, **after** the result is
  declared, and **within two months of the declaration** (late only with sufficient cause).
- **Nearby, about officers, not about the result:** Rule 52-A(8), TN Rules, PDF p.84 (printed p.70):
  > (8) Where the Election Commission, suo-moto or on complaint or on the report of the Observer is of the opinion that a District Election Officer or Electoral Officer or Election Officer by an act or omission or commission has done anything detrimental to the conduct of free and fair election, the Election Commission may recall such District Election Officer or Electoral Officer or Election Officer, as the case may be, and appoint another eligible officer in his place who shall proceed the election as per the election programme already drawn by the Election Commission.

  This lets the Election Commission replace an election officer during an election. It is not a
  route to challenge a declared result.

### Multi-State society: NEARBY

Section 45(1) (substituted by the 2023 Amendment Act), PDF p.6:
> `45. (1) The Central Government shall, by notification, establish an Authority to be known as the Co-operative Election Authority which shall consist of a Chairperson, a Vice-Chairperson and Members not exceeding three to be appointed by the Central Government on the recommendation of the Selection Committee consisting of such persons as may be prescribed.

The file establishes the Authority; other provisions refer to its conduct of elections (p.15, "the
expenses incurred by the Co-operative Election Authority for conduct of elections"; p.19, where
the Authority "has failed to conduct elections"). This file contains **no provision on challenging
an election**. That would be in the consolidated Act and the Rules,
which are not in the repo.
