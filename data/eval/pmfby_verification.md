# PMFBY verification of `tamil_questions.csv` (T01 to T15)

Evidence for a person to read. **Nothing here changes a `status` in the CSV**; only a person
promotes a row to `CHECKED`.

## Source and method

- **Document:** *Pradhan Mantri Fasal Bima Yojana, Revamped Operational Guidelines (Effective
  from Kharif 2020)*, Department of Agriculture, Cooperation and Farmers Welfare. 157 PDF pages.
  Downloaded in this run from
  `https://pmfby.gov.in/pdf/Revamped%20Operational%20Guidelines_17th%20August%202020.pdf`
  (normal TLS verification, starts with `%PDF-1.7`) and saved as
  `data/raw/SCH-PMFBY-GUIDELINES-2020_en.pdf`. The file name of the URL dates it 17 August 2020;
  the cover page itself says "Effective from Kharif 2020". **This is the 2020 version.** A later
  revision may exist; none is in the repo.
- **Companion file read:** `data/raw/SCH-PMFBY-NEW-PROVISIONS_en.pdf` (PIB note). It does
  not mention helpline 14447.
- **Text extraction:** poppler `pdftotext` (`-raw` for paragraph numbers, `-layout` for tables).
  `pdfplumber` and `pypdf` are not installed on this machine and were not downloaded. Every page
  used had clean text; no page needed a second extractor. Quotes join line breaks into single
  spaces and are otherwise exactly as extracted (the PDF's own spacing and punctuation
  glitches, such as "MobileApp", were left alone).
- **Page references:** `PDF p.N` is the page of the PDF file; `printed p.M` is the number at the
  foot of the page (printed = PDF − 9 from the foreword on). Paragraph numbers are the
  guidelines' own.
- **Paragraph numbers in the CSV's `source` column** (5.1.3, 5.1.4, 5.1.8) are not the
  guidelines' numbers; the passages are paras **5.2.3, 5.2.4 and 5.5**.

Verdicts: **MATCH** (the CSV answer is fully supported), **PARTIAL** (supported but incomplete),
**MISMATCH** (the source says something different), **NOT FOUND** (no passage found).

| id | verdict | | id | verdict | | id | verdict |
|---|---|---|---|---|---|---|---|
| T01 | MATCH | | T06 | MATCH | | T11 | PARTIAL |
| T02 | PARTIAL | | T07 | PARTIAL | | T12 | PARTIAL |
| T03 | PARTIAL | | T08 | RESOLVED (see section) | | T13 | **MISMATCH** |
| T04 | MATCH | | T09 | PARTIAL | | T14 | MATCH |
| T05 | MATCH | | T10 | PARTIAL | | T15 | NOT FOUND |

---

## T01

- **Question:** Within how many hours must I report crop damage?
- **CSV expected answer:** Report localized-calamity or post-harvest damage within 72 hours.
- **Evidence (localized calamity)**, para 21.5.4.1 A, PDF p.81 (printed p.72):
  > A. Immediate intimation (within 72 hours) by the insured farmer as detailed in Para 21.6.4.2 below.
- **Evidence (post-harvest)**, para 21.6.3.1 B, PDF p.89 (printed p.80):
  > B. Immediate intimation (within 72 hours) by the insured farmer to Insurance Company through "Crop Insurance App" or any available channel of reporting as detailed in Para 21.6.3.2 below.
- **Also (widespread losses need no intimation)**, para 5.5, PDF p.15 (printed p.6): see T12.
- **Verdict: MATCH.**

## T02

- **Question:** Whom do I report the crop loss to?
- **CSV expected answer:** Directly to the insurance company, the concerned bank or the local agriculture department.
- **Evidence (localized calamity)**, para 21.5.4.2, PDF p.81 (printed p.72):
  > Channel of reporting i.e. Whom to be reported: Intimation may be given within 72 hours by the farmer either directly through the "Crop Insurance App" or dedicated toll-free number, Centralized Call Centre number of concerned Insurance Company. The intimation may also be forwarded through the concerned bank branch, local agriculture department Government/district officials or through the toll free number. The first mode of intimation should be the "Crop Insurance App" and the centralised Toll-Free Number for this purpose. This can be followed by intimation through the Insurance Company's toll free number or through the bank or district officials to Insurance Company for conducting the individual level investigations. The concerned bank/intermediary would verify the insured details like crop insured, sum insured, premium debited and date of debit & remittance for conducting the investigation/assessment.
- Para 21.5.4.3, same page:
  > Reporting of losses will be done through the Crop Insurance App and the Centralised Toll-Free Number (once operationalized), along with other channels. Other Channels will be phased out subsequently.
- Para 21.5.4.4, same page:
  > In case the intimation has been through the concerned bank branch or Government officials, the concerned IC should be informed within the next 48 hours.
- **Evidence (post-harvest)**, para 21.6.3.2, PDF p.89 (printed p.80):
  > Channel of reporting, i.e. Whom to be reported: Intimation may be given within 72 hours by farmer either through the Crop Insurance App or directly to the Insurance Company through the dedicated toll-free number, Centralized Call Centre number, concerned bank branch, local agriculture department, Government./district officials or through the Insurance Company's toll-free number. The first mode of intimation should be through the Crop Insurance App, centralised Toll-Free Number, followed by intimation through Insurance Company's toll-free number for conducting the individual level investigations. Crop loss intimation may also be forwarded through bank or district officials to Insurance Company.
- **Verdict: PARTIAL.** The three CSV channels are named, but the list is incomplete and the
  wording differs: the guideline puts the **Crop Insurance App** and the **centralised toll-free
  number** first, adds the insurance company's **Centralized Call Centre number**, and says the
  bank branch and officials *forward* the intimation to the insurance company. The CSV answer
  says "directly to ... the concerned bank". The guideline does **not** list the National Crop
  Insurance Portal (NCIP) as a place a farmer reports a loss; in these paragraphs NCIP is where
  the company uploads the data (see "Contradictions" below).
- **Corrected English answer:** Intimation may be given within 72 hours by the farmer either
  directly through the "Crop Insurance App" or dedicated toll-free number, Centralized Call
  Centre number of concerned Insurance Company. The intimation may also be forwarded through the
  concerned bank branch, local agriculture department Government/district officials or through
  the toll free number.

## T03

- **Question:** What details must I give when reporting the loss?
- **CSV expected answer:** The insured crop and the area affected, survey number by survey number.
- **Evidence (localized)**, para 21.5.4.1 B, PDF p.81 (printed p.72):
  > B. Intimation must contain details of insured farmer's name, affected survey number-wise insured crop and acreage affected, Farmer's Application No as on NCIP, his/her Mobile Number etc. KCC A/c No. (in case of loanee farmer) or Saving bank Account (in case of Non-Loanee farmer as declared at the time of applying for crop insurance) for identification and verification purpose.
- **Evidence (post-harvest)**, para 21.6.3.1 C, PDF p.89 (printed p.80): same wording ("C. Intimation must contain details of insured farmer's name, affected survey number-wise insured crop and acreage affected, Farmer's Application No as on NCIP, his/her Mobile Number, etc. KCC A/c No. (in case of loanee farmer) or Saving bank Account (in case of Non-Loanee farmer as declared at the time of applying for crop insurance) for identification and verification purpose.").
- Table 10 row 1, PDF p.84 (printed p.75): "Farmer should provide his bank account number (loan account for loanee farmer and savings account for non-loanee farmer) or Enrolment number generated from the portal at the time of intimation."
- **Verdict: PARTIAL.** Crop and acreage "survey number-wise" are in the list, but the answer omits the
  farmer's name, application number, mobile number and the account number.
- **Corrected English answer:** Intimation must contain details of insured farmer's name,
  affected survey number-wise insured crop and acreage affected, Farmer's Application No as on
  NCIP, his/her Mobile Number etc. KCC A/c No. (in case of loanee farmer) or Saving bank Account
  (in case of Non-Loanee farmer as declared at the time of applying for crop insurance) for
  identification and verification purpose.

## T04

- **Question:** How much premium does a farmer pay for kharif food grain and oilseed crops?
- **CSV expected answer:** 2% of the sum insured or the actuarial rate, whichever is less.
- **Evidence**, para 13.1, Table 1, PDF p.33 (printed p.24). The table, row by row (the `-table`
  extraction keeps the rows apart):
  > The rate of premium payable by the farmer will be as per the following Table 1: Season / Crops / Maximum Premium Rate payable by farmer (% of Sum Insured)\* — **Kharif:** All Food grain and Oilseeds crops (all Cereals, Millets, Pulses and Oilseeds crops): 2.0% of SI or Actuarial rate, whichever is less.
- **Verdict: MATCH.** The guideline calls it the "**Maximum** Premium Rate payable by farmer".

## T05

- **Question:** What is the premium for rabi food grain and oilseed crops?
- **CSV expected answer:** 1.5% of the sum insured or the actuarial rate, whichever is less.
- **Evidence**, para 13.1, Table 1, PDF p.33 (printed p.24):
  > **Rabi:** All Food grain and Oilseeds crops (all Cereals, Millets, Pulses and Oilseeds crops): 1.5% of SI or Actuarial rate, whichever is less.
- **Verdict: MATCH.**

## T06

- **Question:** What premium does a farmer pay for horticultural and commercial crops?
- **CSV expected answer:** 5% of the sum insured or the actuarial rate, whichever is less.
- **Evidence**, para 13.1, Table 1, PDF p.33 (printed p.24):
  > **Kharif and Rabi:** Annual Commercial/ Annual Horticultural crops: 5% of SI or Actuarial rate, whichever is less. Perennial horticultural / commercial crops (pilot basis): 5% of SI or Actuarial rate, whichever is less.
  > \*Note: Premium paid by non loanee farmers should be rounded off to nearest Rupee.
- **Verdict: MATCH.** The table says *Annual* Commercial/Horticultural crops (both seasons); the
  perennial pilot crops also pay 5%. The CSV wording would be more exact with "annual".

## T07

- **Question:** Who can join the crop insurance scheme?
- **CSV expected answer:** All farmers growing notified crops in a notified area, including loanee, non-loanee, sharecropper and tenant farmers.
- **Evidence**, para 3.1, PDF p.13 (printed p.4):
  > 3.1 All farmers including sharecroppers and tenant farmers growing the notified crops in the notified areas are eligible for coverage. However, farmers should have insurable interest for the insured crops and lands. Such farmers are required to submit necessary documentary evidence of land records prevailing in the State (Records of Right (RoR), Land Possession Certificate (LPC) etc.) and/or applicable contract/ agreement details/ other documents notified/ permitted by concerned State Government in case of sharecroppers/tenant farmers and the same should be defined by the respective States in the notification itself. Such farmers are also required to essentially submit Aadhaar Number and declaration about the crop sown/ crops intended to be sown.
- Para 3.1.1.1 and 3.1.2: see T08 (loanee and non-loanee farmers are both covered by "optional").
- **Verdict: PARTIAL.** The statement is supported, but it omits the conditions: **insurable interest**,
  land-record evidence, Aadhaar number and the crop declaration.
- **Corrected English answer:** All farmers including sharecroppers and tenant farmers growing
  the notified crops in the notified areas are eligible for coverage. However, farmers should
  have insurable interest for the insured crops and lands.

## T08 (the conflict)

- **Question:** Must a farmer who took a crop loan take the insurance?
- **CSV expected answer:** a warning note, not an answer; there is nothing to grade.
- **Evidence, loanee farmers**, para 3.1.1 and 3.1.1.1, PDF p.13 (printed p.4):
  > 3.1.1 Farmers availing the Kisan Credit Card (KCC)/Crop loan/Loanee Farmers:
  > 3.1.1.1 The scheme is optional for all farmers including farmers who have been sanctioned short-term Seasonal Agricultural Operations (SAO) loans/Kisan Credit Card (KCC) for the notified crops from defined FIs (hereinafter referred to as Loanee farmers). Existing Loanee farmers who do not want to get covered under the scheme have the option of opting-out from the Schemes by submitting requisite declaration to loan sanctioning bank branches any time during the year but at least seven days prior to the cut-off date for enrolment of farmers for the respective season. All those farmers who do not submit the declaration would be essentially covered.
- **Evidence, non-loanee farmers**, para 3.1.2, PDF p.13 (printed p.4):
  > 3.1.2 Other Farmers/Non-loanee Farmers: As mentioned in Para 3.1.1.1 above, the Scheme is optional for all farmers including non-loanee farmers/other farmers.
- **Evidence, how the opt-out works**, para 17.5.11, PDF p.45 (printed p.36):
  > 17.5.11 The scheme will work on the "Opt-out" mode for the existing loanee farmers. The farmers can choose not to be enrolled under the Scheme, by giving a signed declaration as per prescribed format, mentioning his/her unwillingness to participate in the schemes any time during the year for the upcoming season but atleast 7 days before the cut-off date for enrolment/debiting premium.
- Para 17.5.14 and 17.5.15, PDF p.46 (printed p.37):
  > 17.5.14 Declaration for both "Opting in" and for "Opting out" will have to be submitted by the farmer in the same bank where they have their KCC/SAO Loan account. [...] 17.5.15 Banks will ensure enrolment of all those loanee farmers who have Opted-in, or have not submitted declarations for Opting-out upto 7 days before the cut-off date for enrolment/debiting of premium.
- **Version:** *Revamped Operational Guidelines of PMFBY (Effective from Kharif 2020)*, the version
  in this run (file dated 17 August 2020).
- **Finding:** the scheme is **optional** for loanee and non-loanee farmers alike. For an existing
  loanee farmer it works in **opt-out** mode: covered by default, unless the farmer submits an
  opt-out declaration to the bank at least 7 days before the enrolment cut-off date. The answer
  is neither plain "compulsory" nor plain "voluntary".
- **What the repo says:**
  - `backend/services/data/schemes.yaml` (the file the CSV's `source` column cites) says
    "Loanee farmers availing Seasonal Agricultural Operations (SAO) loans are covered
    compulsorily for notified crops." **This contradicts paras 3.1.1.1 and 17.5.11.** (It also
    says "Non-loanee farmers can enroll voluntarily via the National Crop Insurance Portal or
    banks/CSC", which agrees with 3.1.2 and 17.6 to 17.7.)
  - `backend/data/schemes.yaml` (the file the API serves) made **no** loanee claim before this
    run: its `eligibility` fact was a placeholder.
- **Verdict:** no CSV answer to grade. Against the source, the repo's "covered compulsorily" claim
  is a **MISMATCH**.

## T09

- **Question:** How can a farmer without a loan enrol?
- **CSV expected answer:** Voluntarily through the National Crop Insurance Portal, a bank or a CSC.
- **Evidence**, para 17.6.1, PDF p.46 (printed p.37):
  > 17.6 Non-Loanee farmers through Banks and other channel partners: 17.6.1 All non-loanee farmers desirous of availing crop insurance shall fill up the application form of the Scheme and submit the same to nearest bank branch/CSCs or authorized channel partner or insurance intermediary of insurance company.
- Para 17.7.1 and 17.7.2, PDF p.47 (printed p.38):
  > 17.7 Non-Loanee Farmers - directly to ICs/Web Portal: 17.7.1 Non-Loanee farmer may submit insurance proposals personally to Insurance Company with requisite/desired supporting documents and applicable premium has to be remitted electronically to concerned Insurance Company and details of UTR/remittance slips should compulsorily be attached with application. 17.7.2 Non-loanee farmer can also submit application forms for getting insurance coverage through NCIP / Crop Insurance App. For this, farmer can fill up the online application form available on NCIP (www.pmfby.gov.in) / Crop Insurance App and pay the requisite premium through payment gateway.
- Para 17.7.3, same page: "It is mandatory that Non-Loanee farmers, personally submitting proposals to Insurance Company or through NCIP, should have insurable interest and submit necessary documentary evidence as proof as decided by SLCCCI along with Aadhaar Number or Aadhaar Enrolment Number."
- "Voluntarily": para 3.1.2 (see T08).
- **Verdict: PARTIAL.** The three channels named are supported, but the list is not complete: it
  omits the **Crop Insurance App**, applying **personally to the Insurance Company**, and
  authorized channel partners or insurance intermediaries, and the Aadhaar and insurable-interest
  requirement.
- **Corrected English answer:** All non-loanee farmers desirous of availing crop insurance shall
  fill up the application form of the Scheme and submit the same to nearest bank branch/CSCs or
  authorized channel partner or insurance intermediary of insurance company. Non-loanee farmer
  can also submit application forms for getting insurance coverage through NCIP / Crop Insurance
  App.

## T10

- **Question:** Is a crop damaged by hailstorm covered?
- **CSV expected answer:** Yes. Hailstorm, landslide, inundation, cloudburst and lightning fire on an individual farm are covered localized risks; the farmer must report it.
- **Evidence**, para 21.5.1, PDF p.80 (printed p.71):
  > 21.5.1 The Scheme provides for insurance cover at the individual farm level to crop losses due to occurrence of localized perils/ calamities viz. hailstorm, landslide, inundation, cloud burst and natural fire due to lightening affecting part of a notified unit or a plot.
- Para 21.5.3.1, same page:
  > 21.5.3.1 This add-on cover will only be available if this cover is notified by the State Government.
- Para 21.5.3.5, PDF p.81 (printed p.72):
  > 21.5.3.5 Only those farmers would be eligible for financial support under this cover who have paid the premium i.e. the premium has been debited from their account before the occurrence of the insured peril.
- Para 21.5.7 E, PDF p.82 (printed p.73):
  > E. Intimation of crop losses is compulsory for individual insured farmers through various channels in case of losses due to specified localized calamities.
- Hailstorm is also a basic-cover peril for yield loss, para 5.1, PDF p.14 (printed p.5): "...due to non-preventable risks like drought, dry spells, flood, inundation, wide spread pest and disease attack, landslides, natural fire due to lightening, storm, hailstorm, and cyclone."
- **Verdict: PARTIAL.** Supported, but the answer leaves out the conditions: the localized cover
  applies only if the **State notifies** it, and only farmers whose **premium was debited before the
  peril** are eligible.
- **Corrected English answer:** The Scheme provides for insurance cover at the individual farm
  level to crop losses due to occurrence of localized perils/ calamities viz. hailstorm,
  landslide, inundation, cloud burst and natural fire due to lightening. This add-on cover will
  only be available if this cover is notified by the State Government. Intimation of crop losses
  is compulsory for individual insured farmers through various channels in case of losses due to
  specified localized calamities.

## T11

- **Question:** What if harvested crop drying in the field is damaged?
- **CSV expected answer:** Cover applies for up to two weeks from harvest for crop drying in the field; it must be reported.
- **Evidence**, para 5.2.3, PDF p.15 (printed p.6):
  > 5.2.3 Post-Harvest Losses: Coverage is available only up to a maximum period of two weeks from harvesting, for those crops which are required to be dried in cut and spread / small bundled condition depending on requirement of the crops in that area, in the field after harvesting against specific perils of hailstorm, cyclone, cyclonic rains and unseasonal rains.
- Para 21.6.1, PDF p.88 (printed p.79):
  > 21.6.1 Provision has been made for assessment of loss on individual plot basis in the case of occurrence of hailstorm, cyclone, cyclonic rains and unseasonal rains resulting in damage to harvested crop lying in the field in 'cut and spread'/small bundled condition depending on nature of the crop in that area kept solely to dry upto a maximum period of two weeks (14 days) from harvesting. [...] The States/UTs have to compulsorily notify the crops to be included under post-harvest losses along with the harvesting window in the Bid Document, Notification and on the NCIP. The crops not falling under the aforesaid category/not included in the tender shall not be included later for post-harvest loss cover.
- Para 21.6.2.1, same page: "21.6.2.1 This Add-on cover will only be available if this cover is notified by the State Government."
- Para 21.6.3.5, PDF p.89 (printed p.80): "21.6.3.5 Intimation of crop losses is compulsory for individual insured farmers through various channels in case of losses due to specified Post Harvest Calamities."
- **Verdict: PARTIAL.** The two-week limit and the duty to report are supported. Missing: the
  cover applies only to **crops the State has notified** for post-harvest cover, and only for the
  perils **hailstorm, cyclone, cyclonic rains and unseasonal rains**.
- **Corrected English answer:** Coverage is available only up to a maximum period of two weeks
  from harvesting, for those crops which are required to be dried in cut and spread / small
  bundled condition, in the field after harvesting against specific perils of hailstorm,
  cyclone, cyclonic rains and unseasonal rains. This Add-on cover will only be available if this
  cover is notified by the State Government. Intimation of crop losses is compulsory for
  individual insured farmers through various channels in case of losses due to specified Post
  Harvest Calamities.

## T12

- **Question:** Do I have to report a widespread loss such as drought separately?
- **CSV expected answer:** No. For widespread calamities the claim is based on the state's loss assessment or average yield.
- **Evidence**, para 5.5, PDF p.15 (printed p.6):
  > 5.5 Loss/damage for localised calamities and post-harvest losses will be assessed at the level of the individual insured farm and hence lodging of loss intimation by the farmer/designated agencies is essential. For remaining risks, losses are due to widespread calamities, hence lodging of intimation for claims by insured farmers / designated agencies for such wide-spread calamities is not essential. Claims will be calculated based on the loss assessment report submitted by the District Level Joint Committee (DLJC) and/or average yield submitted by concerned State Government.
- **Verdict: PARTIAL.** "No" is supported ("lodging of intimation ... is not essential"). The basis
  of the claim is mis-stated: the guideline says the **loss assessment report of the District Level
  Joint Committee (DLJC)** and/or the **average yield submitted by the State Government**, not "the
  state's loss assessment".
- **Corrected English answer:** Lodging of intimation for claims by insured farmers /
  designated agencies for such wide-spread calamities is not essential. Claims will be
  calculated based on the loss assessment report submitted by the District Level Joint Committee
  (DLJC) and/or average yield submitted by concerned State Government.

## T13

- **Question:** Within what time must the loss assessment happen?
- **CSV expected answer:** Within 72 hours of the company appointing the loss assessor.
- **Evidence (localized)**, para 21.5.7, PDF p.82 (printed p.73):
  > 21.5.7 Time frame for loss assessment and submission of the report: A. Appointment of loss assessor within 48 hours. B. Loss assessment to be completed within the next 10 days. C. Claim settlement to be completed in next 15 days (subject to receipt of farmers premium& first instalment of Subsidy).
- Table 10 (para 21.5.10), PDF p.85 (printed p.76), rows 3 to 5 (the schedule cell for rows 4 and 5 is merged in the PDF):
  > 3: Appointment of loss assessor as per qualifications & experience laid down in the OGs of PMFBY. Insurance company. Within 48 hours from the receipt of the information / intimation.
  > 4: Assessment of affected area in term of % of area sown. DLJC. / 5: Individual level assessment of loss (in case the affected area is < 25% of the total cropped area). Jointly by the Insurance Company & block level Agriculture Officer. Within 10 days of the appointment of the loss assessor by the company.
  > 7: Claim-payment to affected farmers. Insurance company. Within 15 days from receipt of loss assessment report subject to receipt of at-least advance Government share of subsidy (1st instalment of both State & Central Government).
- **Evidence (post-harvest)**, para 21.6.6, PDF p.91 (printed p.82):
  > 21.6.6.1 Appointment of the loss assessor within 48 hours from the receipt of information. 21.6.6.2 Loss assessment to be completed within next 10 days. 21.6.6.3 Claim settlement/payment to the farmers to be completed in next 15 days (subject to receipt of premium) from the time of receipt of loss assessment report.
- **Verdict: MISMATCH.** "72 hours" is the **farmer's intimation** window. For the loss assessment the
  guidelines give **10 days**, counted from the appointment of the loss assessor, and the loss
  assessor is to be appointed within **48 hours** of the intimation. No passage ties a 72-hour
  limit to the assessment.
- **Corrected English answer:** Loss assessment is to be completed within the next 10 days, that
  is within 10 days of the appointment of the loss assessor by the company; the loss assessor is
  to be appointed within 48 hours from the receipt of the information / intimation.

## T14

- **Question:** How fast must the bank give verification of the premium payment?
- **CSV expected answer:** Within 48 hours of receiving the request.
- **Evidence (localized)**, para 21.5.4.1 C, PDF p.81 (printed p.72):
  > C. Premium payment verification to be done from the portal and in case of need, may be verified from the bank. The bank shall provide the payment verification within the next 48 hours of receipt of such request.
- **Evidence (post-harvest)**, para 21.6.3.1 D, PDF p.89 (printed p.80):
  > D. Premium payment verification to be done from the portal and in case required, may be verified from the bank and bank shall provide the payment verification within next 48 hours of receipt of such request.
- **Who acts:** the bank. **From when:** receipt of the request for verification (the guideline does
  not say who makes the request). The check is first done "from the portal"; the bank is asked
  only "in case of need".
- **Verdict: MATCH.**

## T15

- **Question:** What helpline can I call with a crop insurance complaint?
- **CSV expected answer:** Register grievances through the Krishi Rakshak Portal and Helpline, 14447.
- **Search:** the guidelines (all 157 pages) and the PIB note contain neither "14447" nor "Krishi
  Rakshak" nor "helpline". The CSV cites a PIB press release URL that is not in the repo.
- **What the guidelines do say about numbers,** para 21.5.4.2, PDF p.81 (printed p.72): "Intimation
  may be given within 72 hours by the farmer either directly through the "Crop Insurance App" or
  dedicated toll-free number, Centralized Call Centre number of concerned Insurance Company."
  No number is given.
- **Verdict: NOT FOUND** in the available sources. `backend/services/data/forums.yaml` lists 14447
  with `source_url: https://pmfby.gov.in/contact`, which could not be checked here (not in the
  repo). A person has to confirm it on that page.

---

## Contradictions with what the repo says

1. **Loanee enrolment (T08):** `backend/services/data/schemes.yaml` says loanee farmers "are
   covered compulsorily". The guidelines (paras 3.1.1.1, 17.5.11) say the scheme is optional and
   works in opt-out mode.
2. **Loss reporting channels (the `loss` fact):** `backend/data/schemes.yaml`, `backend/services/data/schemes.yaml`,
   `backend/data/demo_answers.yaml` and the Hindi/Tamil texts in `backend/services/data/fastpath_text.yaml`
   all name the **National Crop Insurance Portal (NCIP)** as a place to report a loss. Paras 21.5.4.2
   and 21.6.3.2 name the Crop Insurance App, the toll-free number, the Centralized Call Centre
   number, the bank branch and local agriculture officials; they do not name NCIP. A search of
   the whole document found NCIP only as where the insurance company, the State and the bank
   upload loss and premium data (for example paras 21.5.7 E, 21.6.3.5, 23.3 and 23.4).
3. **`loss` fact source label:** it cites "sections 21.4 and 21.5". Section 21.4 is On-Account
   payment for mid-season adversity. The loss-reporting rules are in **21.5** (localized
   calamity) and **21.6** (post-harvest).
4. **T13 (CSV):** "72 hours" for the assessment is wrong (see T13). `services/data/schemes.yaml` and the
   `loss` fact do not make that claim.
5. **Premium rates:** `backend/services/data/schemes.yaml` (2.0%, 1.5%, 5.0%) agrees with Table 1.
