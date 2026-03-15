# 1️⃣ Judgment collection

First the raw judgment is obtained from courts such as the Supreme Court of India or a High Court.

Sources can include:

- court websites

- registry copies

- internal reporting networks

- official reporters

At this stage the file is usually:

- PDF

- Word document

- scanned text

It often contains formatting issues.

---

# 2️⃣ Text cleaning and formatting

Editorial staff convert the judgment into **structured text**.

Tasks include:

- fixing OCR errors

- correcting paragraph breaks

- standardizing judge names

- formatting case title and citation

Example transformation:

Raw court document:

```
STATE OF BIHAR VS XYZ
Date: 12/05/2023
```

Standardized database format:

```id="axm9i4"
Case Name: State of Bihar v XYZ
Court: Supreme Court
Bench: Justice A, Justice B
Date: 12 May 2023
```

This becomes the **base record of the case**.

---

# 3️⃣ Editorial legal analysis

Now a **legal editor actually reads the judgment**.

They identify:

- key legal issues

- statutes involved

- precedents cited

- final ruling

This step is what turns a raw judgment into **research-ready legal material**.

---

# 4️⃣ Headnote creation

Editors then write **structured headnotes**.

Example format:

```id="9yvtm2"
Criminal Law — Evidence — Dying declaration —
Statement recorded when victim allegedly unconscious —
Declaration held unreliable.
```

Headnotes are extremely condensed summaries of legal principles.

They allow lawyers to scan **hundreds of cases quickly**.

---

# 5️⃣ Ratio extraction

Editors determine the **binding legal principle** (ratio decidendi).

Example:

```id="i0sd1r"
Ratio: Delay in FIR does not automatically
invalidate prosecution case if explanation
for delay is reasonable.
```

This requires interpretation of judicial reasoning.

---

# 6️⃣ Citation mapping

Next editors identify all precedents cited in the judgment.

Example:

```id="hqlhpa"
State of Punjab v Gurmit Singh (1996) 2 SCC 384 — relied on
ABC v Union of India (2010) 4 SCC 700 — distinguished
```

These links are entered into the **citation index**.

This is how SCC builds its **precedent network**.

---

# 7️⃣ Statute tagging

Editors identify which statutory provisions were discussed.

Example tags might include:

- Section 302 – Indian Penal Code

- Section 154 – Code of Criminal Procedure

- Article 21 – Constitution of India

This enables statute-based research.

---

# 8️⃣ Legal taxonomy tagging

The judgment is then categorized within SCC’s internal legal taxonomy.

Example:

```id="i6h1yv"
Criminal Law
   Evidence
      Dying Declaration
         Reliability
```

These topic tags power their **legal subject index**.

---

# 9️⃣ Citation normalization

Many judgments cite cases in different formats.

Example:

```
AIR 1996 SC 1393
(1996) 2 SCC 384
```

Editors link these to **one canonical case record**.

Without this step the database would become inconsistent.

---

# 🔟 Final editorial review

Before publication:

- senior editors verify headnotes

- citations are checked

- formatting is standardized

The goal is to ensure the case is **accurate and legally reliable**.

---

# 1️⃣ Publication in the database

Finally the report is generated with:

- headnotes

- full judgment

- citation links

- topic classification

- statute references


