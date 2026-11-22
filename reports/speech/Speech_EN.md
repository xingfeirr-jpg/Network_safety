# Project 17 Presentation Script (English)

> Comparing three static vulnerability detectors on ten open-source C libraries · with live UI demo
> Suggested length: about 12–15 minutes (sections marked ⏱ can be shortened)
> Demo: local `http://localhost:8000` (with live runs) or the GitHub Pages static site
> **[Action]** = what to do in the UI; plain text = what to say

---

## 0. Opening (about 30 s)

Good morning, everyone. We are the Project 17 team. Our topic is **comparing three static vulnerability detectors on ten open-source C libraries**.

Let me start with a question: when a static analysis tool says "possible buffer overflow", can you trust it? Our approach was simple. We took all **725 alerts** that three tools reported on ten libraries, **checked every single one against the source code**, and then used those verdicts to evaluate the tools themselves.

I'll walk you through it using the web interface we built, following its tabs from left to right.

---

## 1. Overview (about 1 min)

**[Action]** Open the "Overview" tab.

This page summarizes the whole project.

- **Three tools**: Flawfinder, Cppcheck, and CodeChecker with the Clang Static Analyzer, which I'll call "clangsa".
- **Ten open-source C libraries** across six domains: compression, JSON, YAML, XML, images and Unicode.
- **Thirty runs** in total, producing **725 alerts**.

The chart on the right shows the review outcome. Here is the headline: of the 725 alerts, **648 are false positives, 62 are supported, and 15 are undetermined**. In other words, for almost nine out of ten alerts, the risk disappears once you read the code.

The cards below link to each module; let's go through them in order.

---

## 2. Libraries (about 1 min)

**[Action]** Click the "Libraries" tab.

These are the ten libraries. Each one is **pinned to an exact commit**, and we recorded the SHA-256 of the source archive, so we know we are always analyzing the same code.

Two numbers need explaining:

- **Compile actions**: Cppcheck and clangsa analyze one compilation at a time. libjpeg-turbo, for example, is built three times — 8-, 12- and 16-bit — so 58 source files become 101 compile actions.
- **Flawfinder files**: Flawfinder doesn't compile anything; it just reads text, so both `.c` and `.h` files count.

**[Action]** Switch libraries in the pie chart.

The pie chart shows which tool raised each library's alerts and what the verdicts were. Notice how differently the three tools behave on the same library.

---

## 3. Tools (about 1.5 min)

**[Action]** Click the "Tools" tab.

All three tools are static: they never run the program, they only read the code. The difference is how deeply they read. An analogy:

- **Flawfinder searches for keywords** — like raising an alarm whenever the word "bomb" appears in an article. It scans line by line and flags dangerous function names such as `memcpy`, `strcpy` or `strlen`. No build needed, extremely fast, but it doesn't understand the code.
- **Cppcheck reads the sentences** — it tracks the possible values of variables and checks whether they are used correctly. It needs a compilation database.
- **clangsa plays out the whole story** — it uses the real Clang front end, treats inputs as unknowns, and simulates every branch to see whether an error state is reachable. The deepest analysis, and the slowest.

**[Action]** Scroll down to "The matching rules of each tool".

Here are each tool's reporting dimensions and counting rules. For Cppcheck, for example, we count only non-informational findings, and a finding with several locations counts once. **Only with consistent counting rules can the three tools be compared fairly.**

---

## 4. Live Run (about 2 min) ⏱ if short on time, explain the flow without running it

**[Action]** Click "Live Run".

This page shows that our experiment is **reproducible on the spot**. At the top are the six steps:

- S1 Download: fetch the pinned commit and verify its hash
- S2 Source: unpack and hash every file
- S3 Build: build with the original CMake options and export the compilation database
- S4 Command: generate tool commands byte-identical to the original study
- S5 Run: run the tool, recording time and memory with GNU time
- S6 Compare: compare this run with the original, alert by alert

**[Action]** Select zlib + Flawfinder and click "Start run".

The backend is now running the tool inside a Docker container with pinned versions: Flawfinder 2.0.20, Cppcheck 2.13.0, CodeChecker 6.29.1 and Clang 18.1.3.

**[Action]** When it finishes, point to the result.

Done. This run produced **49 alerts — exactly the same 49 as the original study**. Anyone who clones our repository can get the same result.

---

## 5. Dashboard (about 1.5 min)

**[Action]** Click "Dashboard".

This is the full picture of the 725 alerts.

- **Verdicts by tool**: Flawfinder raised 536 alerts — more than 70% of the total — but only **5** are supported. Cppcheck raised 116, with **39** supported. clangsa raised 73, with **18** supported.
- **Run time**: the gap is just as large. Flawfinder's median run takes **0.13 seconds**, Cppcheck **5.44 seconds**, and clangsa **28.33 seconds** — more than 200 times slower than Flawfinder.
- **Top rules**: Flawfinder's top three are `memcpy`, `strlen` and `char` — all name-matching rules.

**[Action]** Filter the alert list and open any alert.

Every alert can be opened to see its location, rule, source line and — most importantly — **the review reasoning**: why it was judged a false positive, or why it is supported. This is the evidence behind all 725 verdicts.

---

## 6. Case Analysis (about 3.5 min)

**[Action]** Click "Case Analysis".

We grouped the 725 alerts into 19 case families by the logic of their verdicts. I'll pick the three most representative: **why the shallowest tool goes wrong, why even the deepest tool goes wrong, and what a real problem looks like**.

### Case 1: A variable named `strlen` — 18 Flawfinder alerts (false positive · name match, not a call)

**[Action]** Open the "Name match, not a call" family and show the utf8proc example.

```c
utf8proc_iterate(const utf8proc_uint8_t *str, utf8proc_ssize_t strlen, utf8proc_int32_t *dst) {
  ...
  if (!strlen) return 0;                     // is the length zero?
  end = str + ((strlen < 0) ? 4 : strlen);   // use the length as the read bound
```

utf8proc has an **integer parameter** that happens to be called `strlen`. It's a length: the code checks whether it is zero and then uses it to compute the read bound. **The `strlen` function is never called.**

But Flawfinder only looks at names. It sees `strlen` and reports "possible over-read". In utf8proc alone, Flawfinder raised **18 alerts — every one of them on this `strlen`, and every one a false positive**. Cppcheck and clangsa understand that it is a variable and report nothing.

This "the name matches, but it isn't a call" family accounts for **70 alerts across 9 libraries**. It shows Flawfinder's fundamental limit: **it doesn't understand syntax, so it cannot tell a function from a variable.**

### Case 2: "Exit on error" — even deep tools get it wrong (false positive · error handler does not return)

**[Action]** Open the "Error handler does not return" family and show libjpeg-turbo `jdapistd.c:211`.

```c
  if (!xoffset || !width)                    // line 207
    ERREXIT(cinfo, JERR_BAD_CROP_SPEC);      // line 208

  /* xoffset and width must fall within the output image dimensions. */
  if (*width == 0 ||                         // line 211
```

clangsa reports a possible null dereference of `width` at line 211. Its reasoning: if `width` is null, execution can reach line 211.

But at lines 207–208, a null `width` first triggers `ERREXIT`. That macro calls the error callback `error_exit`, and libjpeg's documentation states clearly that this callback **must not return** — the default implementation calls `exit`, and a custom one must `longjmp` away. So a null pointer **can never reach line 211**.

clangsa reported this line twice — once for the 8-bit build and once for the 12-bit build — and Cppcheck reported it too. This family contains **88 alerts** from all three tools, almost all in libjpeg-turbo.

The lesson: **even the deepest path analysis cannot see a contract that lives in the documentation.** If the tool doesn't know a function never returns, it invents a path that doesn't exist.

### Case 3: zlib's `memcpy` really can overflow (supported · conditional overflow)

**[Action]** Open the "Conditional overflow" family and show zlib `gzwrite.c:217`.

```c
            copy = state->size - have;           // line 214: space left
            if (copy > len)
                copy = (unsigned)len;
            memcpy(state->in + have, buf, copy); // line 217
```

The first two cases were false positives. Now a **supported** one.

The capacity check here assumes that the amount already buffered, `have`, never exceeds the buffer size `size`. But in **non-blocking** mode, `gzprintf` can legitimately leave `have` between `size` and `2 × size`. A following small `gzwrite` then makes the unsigned subtraction `size - have` **wrap around** to a huge number, so `copy` is no longer limited, and `memcpy` writes **past the end of the heap buffer**.

Here is the interesting part: this supported alert was **reported only by Flawfinder**. Neither Cppcheck nor clangsa flagged it. The noisiest tool caught something the other two missed.

To be clear about the limits: this is a **source-level** derivation. We did not reproduce it dynamically, and we did not assess whether it is remotely exploitable.

**Summary of the three cases**: shallow tools produce false positives because they don't understand syntax; deep tools produce false positives because they don't know the project's conventions; and real problems may hide in the noisiest tool's output.

---

## 7. Conclusions (about 3 min) — the key part

**[Action]** Click "Conclusion".

Now the conclusions. Every number on this page comes from the reviewed alerts, not from the tools' own counts. We look at three dimensions: **accuracy, cost and coverage**.

### First, accuracy differs enormously

| | Flawfinder | Cppcheck | clangsa |
|---|---|---|---|
| Alerts | 536 | 116 | 73 |
| Supported | 5 | 39 | 18 |
| Precision | **0.9%** | **33.6%** | **24.7%** |
| Alerts to review per supported finding | **107** | **3** | **4** |

To find one supported alert, a reviewer has to read on average **107** Flawfinder alerts — but only **3** for Cppcheck and about **4** for clangsa. That is more than a hundredfold difference in human effort.

### Second, machine cost runs the other way

Flawfinder's median time is **0.13 s** with about 25 MB peak memory; Cppcheck takes **5.44 s**; clangsa **28.33 s** with over 200 MB. And both deeper tools **require the project to be built first** to get a compilation database; Flawfinder needs nothing.

So **machine cost and human cost trade off**: Flawfinder is cheap for the machine and expensive for people; clangsa is the opposite.

### Third, coverage: the tools barely overlap

- Flawfinder raised alerts in **all 10 libraries**, Cppcheck in **6**, clangsa in only **4**.
- Each tool found supported problems in four libraries — but **a different four**:
  - Flawfinder: zlib, libpng, yyjson, libjpeg-turbo
  - Cppcheck: LZ4, cJSON, yyjson, libjpeg-turbo
  - clangsa: zlib, LZ4, libpng, libjpeg-turbo
- The kinds of problems differ too: Cppcheck mostly finds portability and redundancy issues (such as right-shifting negative values or redundant null checks); clangsa finds path-related issues like dead stores and null pointers; Flawfinder occasionally catches a real buffer problem, as in Case 3.

**No single tool can replace the other two.**

### Fourth, which tool for which job

- **Cost-sensitive, just a quick pass**: use Flawfinder to list every dangerous API use — but be ready for heavy manual filtering.
- **Routine quality checks in CI**: Cppcheck offers the best value — the highest precision at an acceptable speed.
- **Deep audits of critical modules**: clangsa's path-sensitive analysis suits cases where a few high-value findings justify the time; run it on core code only.
- **Best of all, combine them**: use one tool for broad coverage to narrow the scope, then another to dig into the hot spots — because their alert sets hardly overlap.

### Fifth, the limits of these conclusions

We should also be clear about where these conclusions **do not** apply:

1. They describe the source code under **our fixed build configuration**, not other versions or real deployments.
2. "Supported" means the issue holds **at source level**; we did **not** verify exploitability dynamically.
3. We covered only **ten C libraries** — no C++ or other languages.
4. Tool versions were pinned; newer versions may behave differently.

---

## 8. Reliability (about 1 min) ⏱ can be shortened

**[Action]** Click "Reliability".

Finally, how do we know these results hold up? Two mechanisms.

**Mechanism one: independent replication.** One member ran the original study and handed over only source hashes and tool versions — no intermediate files. Another member re-ran everything from scratch in a clean Docker environment. Result: **all 30 runs produced identical alerts, and all 30 commands matched byte for byte**. For the 9 libraries with a recorded hash, the source archives matched as well (the original study did not record a hash for cJSON).

**Mechanism two: AI analysis plus stratified human review.** An AI assistant first reviewed all 725 alerts against the source and gave a verdict with reasons. The review plan: the 77 supported and undetermined alerts are **reviewed in full**; the 648 false positives are sampled by "tool × exclusion reason", 200 alerts in total, with a fixed random seed so the sample is reproducible.

To be honest about it: **the human review sheet has been generated but not yet completed**, so we do not yet have agreement figures for the AI verdicts. Also, the replication was done by a team member, not an external third party. These are the next things we need to address.

---

## 9. Closing (about 20 s)

In one sentence: **more alerts don't mean more value, and higher precision doesn't mean better coverage.** Each tool has blind spots; combining them by use case, together with human review, is the reliable approach.

Our code, data and this interface are all open source, and anyone can reproduce every result with Docker. Thank you — we're happy to take questions.

---

## Appendix: likely questions

- **Why does Flawfinder produce so many false positives?** It only does lexical matching. It doesn't understand syntax, macros or conditional compilation, so it flags dangerous names without telling functions from variables, and without knowing which code isn't even compiled in this build.
- **Does "supported" mean "vulnerability"?** No. It means the risk holds at source level. Some of the 62 are portability or code-quality issues (for example, right-shifting negative values depends on the compiler) and may not be exploitable.
- **Why is clangsa's precision lower than Cppcheck's?** clangsa's alerts concentrate on path issues such as null pointers, and conventions like "this error handler never returns" (Case 2) live in documentation it cannot see, which produces false positives.
- **Did timings differ in the replication?** The replication machine was slower — 1.3 to 4.7 times the original times — but the speed ranking of the three tools did not change.
- **Who made the verdicts?** An AI assistant produced the initial verdicts for all 725 alerts against the source; the human review sampling plan is ready, but the review itself is not yet complete.
