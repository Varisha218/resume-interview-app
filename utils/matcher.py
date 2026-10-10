"""Resume <-> job description matching using a local sentence-embedding model.

Combines:
1. Sentence-embedding (SBERT) semantic similarity between the full resume and JD.
2. Weighted skills matching (incorporating Required vs Preferred sections),
   where skill importance is derived dynamically from how the JD actually
   mentions each skill, not from a static per-skill lookup table.
3. Embedding-based partial/semantic skill matching (e.g. recognizing
   "led a team of engineers" relates to "leadership") instead of a
   hand-written synonym dictionary.
4. Certification-only-vs-hands-on-experience checks.
5. ATS readability and compatibility metrics.
"""

import math
import re

from . import semantic_model
from .skills_db import SKILLS_DB, SKILL_ALIASES, SOFT_SKILLS, SKILL_IMPLIES, SKILL_IMPLIES_WEAK

# Embedding cosine-similarity thresholds for treating two skill phrases as a
# semantic match. Tuned against MiniLM's typical similarity ranges: unrelated
# short phrases usually score < 0.3, closely related ones 0.5+.
FULL_MATCH_THRESHOLD = 0.62
PARTIAL_MATCH_THRESHOLD = 0.45
PARTIAL_MATCH_RATIO = 0.6
WEAK_MATCH_THRESHOLD = 0.32
WEAK_MATCH_RATIO = 0.3

# A JD-extracted "section" shorter than this many words is treated as too
# thin to be a reliable, deliberately-written section (e.g. a stray heading
# with nothing real under it) -- see _section_sim_like_for_like, which skips
# the comparison entirely rather than compare against it. Kept low: real JD
# sections are often legitimately short (an Education line is commonly just
# "Bachelor's in CS or related field required"), and a short-but-real
# section should still count.
MIN_JD_SECTION_WORDS = 3

ACTION_VERBS = [
    "developed", "designed", "built", "led", "managed", "created", "implemented",
    "improved", "increased", "decreased", "reduced", "optimized", "launched",
    "coordinated", "analyzed", "automated", "delivered", "achieved", "engineered",
    "spearheaded", "streamlined", "accelerated", "initiated", "established",
    "formulated", "leveraged", "pioneered", "revamped", "maximized", "minimized"
]


def _clean(text: str) -> str:
    text = text.lower()
    # Keep letters, numbers, +, #, ., / and whitespace
    text = re.sub(r"[^a-z0-9\+\#\.\/\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Exact (normalized) heading phrases -> section name. Matching is done
# against the *entire* stripped line after lowercasing and stripping
# punctuation, not a substring search across the whole document. A prior
# version matched these keywords anywhere in the text, so an inline label
# like "Team Project" or a sentence containing "hands-on experience
# configuring..." was treated as a fresh section boundary, and a combined
# heading like "Projects And Experience" registered as two overlapping
# boundaries at once -- both scrambled which content ended up in which
# section. Requiring an exact whole-line match keeps only genuine headings.
_HEADING_TO_SECTION = {
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "relevant experience": "experience",
    "employment": "experience",
    "employment history": "experience",
    "work history": "experience",
    "projects and experience": "experience",
    "experience and projects": "experience",
    "projects": "projects",
    "personal projects": "projects",
    "academic projects": "projects",
    "key projects": "projects",
    "notable projects": "projects",
    "project experience": "projects",
    "technical projects": "projects",
    "education": "education",
    "academic background": "education",
    "educational background": "education",
    "qualifications": "education",
    "skills": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "technologies": "skills",
    "key skills": "skills",
    "skills and technologies": "skills",
    "summary": "summary",
    "objective": "summary",
    "profile": "summary",
    "about me": "summary",
    "professional summary": "summary",
    "career summary": "summary",
    # Job-description-style headings. JDs almost never reuse resume section
    # names -- they describe the same ground (day-to-day work, required
    # background, required tools) under their own vocabulary. Without these,
    # a real JD ends up with zero recognized sections, which forces every
    # resume section to be compared against the JD's *entire* text instead
    # of the relevant part of it, silently deflating the contextual score
    # for virtually every real-world JD.
    "responsibilities": "experience",
    "key responsibilities": "experience",
    "role responsibilities": "experience",
    "job responsibilities": "experience",
    "roles and responsibilities": "experience",
    "duties": "experience",
    "duties and responsibilities": "experience",
    "what you ll do": "experience",
    "what you will do": "experience",
    "day to day responsibilities": "experience",
    "core responsibilities": "experience",
    "required qualifications": "education",
    "minimum qualifications": "education",
    "basic qualifications": "education",
    "education requirements": "education",
    "preferred qualifications": "experience",
    "nice to have": "experience",
    "bonus skills": "skills",
    "required technical skills": "skills",
    "technical requirements": "skills",
    "required skills": "skills",
    "preferred skills": "skills",
}


def _normalize_heading_line(line: str) -> str:
    line = line.lower()
    line = re.sub(r"[^a-z\s]", " ", line)
    return re.sub(r"\s+", " ", line).strip()


def _restore_glued_headings(text: str) -> str:
    """Recover a section heading that PDF text extraction glued onto the end
    of the previous line, e.g. '...ahead of Play Store and App Store
    releases.Projects And Experience' (the line break before the heading was
    dropped, so 'Projects And Experience' silently never gets recognized as
    a heading, and that whole section's content gets swallowed into
    whatever section came before it).

    We deliberately do NOT search for heading words anywhere in a line --
    that's the earlier bug already noted above (an inline label or a
    sentence merely containing a heading word getting mistaken for a
    section boundary). Instead we only act when a heading phrase is glued
    directly onto prior text with zero whitespace between them: normal
    prose always has a space after a period/word, so its total absence
    right before an exact known heading phrase is a specific, safe signal
    of a lost line break rather than a heading keyword occurring in prose.
    """
    for heading in sorted(_HEADING_TO_SECTION, key=len, reverse=True):
        pattern = re.compile(
            r"(?<=\S)(" + re.escape(heading).replace(r"\ ", r"\s+") + r")(?=[\s:]|$)",
            re.IGNORECASE,
        )
        text = pattern.sub(lambda m: "\n" + m.group(1), text)
    return text


def _extract_sections(text: str) -> dict:
    text = _restore_glued_headings(text)
    positions = []
    offset = 0
    for line in text.split("\n"):
        norm = _normalize_heading_line(line)
        name = _HEADING_TO_SECTION.get(norm)
        if name:
            positions.append((offset, name))
        offset += len(line) + 1  # +1 for the newline consumed by split("\n")
    positions.sort(key=lambda x: x[0])

    sections = {}
    for i, (pos, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        content = text[pos:end].strip()
        # Remove the heading itself from the content (usually first line)
        content = re.sub(r"^[^\n]*\n", "", content, count=1).strip()
        if content:
            sections[name] = content
    return sections


def _find_skills(text: str):
    text_clean = f" {_clean(text)} "
    
    # Build list of terms: (term_to_search, canonical_name)
    search_terms = []
    for skill in SKILLS_DB:
        search_terms.append((skill, skill))
    for alias, canonical in SKILL_ALIASES.items():
        search_terms.append((alias, canonical))
        
    # Sort terms by length descending so longer/more-specific phrases are
    # considered first conceptually, though matching no longer depends on
    # this order (see below) -- kept for readability/debuggability.
    search_terms.sort(key=lambda x: len(x[0]), reverse=True)

    # Match every term independently against the *original* cleaned text.
    # We intentionally do NOT erase matched spans between terms: the regex
    # word-boundaries (?<![a-z0-9]) / (?![a-z0-9]) already prevent genuine
    # false substring bleed-through (e.g. "java" never matches inside
    # "javascript", since there's no boundary between them). Erasing spans
    # used to cause real skills to disappear whenever they were physically
    # embedded inside a longer alias phrase's matched text -- e.g. a resume
    # that says "Suricata IDS" would have that whole phrase matched and
    # masked by the "suricata ids" -> "suricata" alias, deleting the "IDS"
    # characters before the standalone "ids" skill term ever got a chance
    # to match, so a candidate with clear IDS experience was reported as
    # missing IDS entirely. Searching every term against the untouched text
    # lets both the specific alias ("suricata") and the standalone skill
    # it contains ("ids") register as found, which is what should happen.
    found = set()
    for term, canonical in search_terms:
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        if re.search(pattern, text_clean):
            found.add(canonical)

    return found


def _get_jd_skills_with_priority(jd_text: str, jd_skills: set) -> dict:
    jd_text_lower = jd_text.lower()
    preferred_keywords = ["preferred", "plus", "desired", "nice to have", "advantages", "beneficial", "optional"]
    required_keywords = ["required", "requirements", "must have", "qualifications", "experience required", "essential"]
    
    skills_priority = {}
    lines = jd_text_lower.split("\n")
    current_priority = "required"
    
    for line in lines:
        if any(kw in line for kw in preferred_keywords):
            current_priority = "preferred"
        elif any(kw in line for kw in required_keywords):
            current_priority = "required"
            
        for skill in jd_skills:
            pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
            if re.search(pattern, f" {line} "):
                if skill not in skills_priority or current_priority == "required":
                    skills_priority[skill] = current_priority
                    
    for skill in jd_skills:
        if skill not in skills_priority:
            skills_priority[skill] = "required"
            
    return skills_priority


def _check_certification_only(resume_text: str, skill: str) -> bool:
    text_lower = resume_text.lower()
    pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
    occurrences = list(re.finditer(pattern, text_lower))
    if not occurrences:
        return False
        
    cert_keywords = ["certification", "certifications", "certified", "exam", "fundamentals", "course", "degree", "credential", "license"]
    
    cert_only_count = 0
    for match in occurrences:
        start = max(0, match.start() - 35)
        end = min(len(text_lower), match.end() + 35)
        context = text_lower[start:end]
        if any(kw in context for kw in cert_keywords):
            cert_only_count += 1
            
    return cert_only_count == len(occurrences)


def _check_partial_match(jd_skill: str, resume_skills: set) -> tuple:
    """Compare jd_skill against every skill phrase found in the resume.

    Returns (ratio, tier, best_resume_skill, score):
    - ratio: score contribution toward skill_match (0.0-1.0)
    - tier: "full" | "partial" | "weak" | "none"
    - best_resume_skill: the closest resume skill found (for surfacing to the user)
    - score: the raw embedding similarity behind that tier decision, so
      callers can judge how confident the "closest thing found" evidence
      actually is (e.g. a bare pass of WEAK_MATCH_THRESHOLD is too weak a
      signal to state as a specific relation to the user)

    The "weak" tier exists for cases like a resume that mentions "Kotlin" and
    "Firebase" for an Android app but never literally writes the word
    "Android" -- a human reviewer would reasonably infer it, but it's not a
    confirmed statement either. Those get flagged separately as "worth
    clarifying" instead of being penalized the same as a true gap.
    """
    if jd_skill in resume_skills:
        return 1.0, "full", jd_skill, 1.0

    if not resume_skills:
        return 0.0, "none", None, 0.0

    # Ask the embedding model how semantically close jd_skill is to each
    # skill phrase actually found in the resume, and take the best match.
    # This is what replaces the old hand-written SEMANTIC_PARTIAL_MATCHES
    # synonym dictionary -- the model itself decides that e.g. "leadership"
    # and "mentoring" are related, rather than a human enumerating pairs.
    resume_skills_list = list(resume_skills)
    sims = semantic_model.similarity_matrix([jd_skill], resume_skills_list)[0]
    best_idx = int(sims.argmax())
    best_score = float(sims[best_idx])
    best_skill = resume_skills_list[best_idx]

    if best_score >= FULL_MATCH_THRESHOLD:
        return 1.0, "full", best_skill, best_score
    if best_score >= PARTIAL_MATCH_THRESHOLD:
        return PARTIAL_MATCH_RATIO, "partial", best_skill, best_score
    if best_score >= WEAK_MATCH_THRESHOLD:
        return WEAK_MATCH_RATIO, "weak", best_skill, best_score
    return 0.0, "none", None, best_score


def _check_ats_compatibility(resume_text: str) -> dict:
    text_lower = resume_text.lower()
    word_count = len(resume_text.split())
    
    searchable = len(resume_text.strip()) > 200
    
    headings = ["experience", "education", "skills", "projects"]
    found_headings = []
    for h in headings:
        if any(syn in text_lower for syn in [h, h + "s", "work " + h, "academic " + h]):
            found_headings.append(h)
    standard_headings = len(found_headings) >= 3
    
    has_complex_tables = text_lower.count("|") > 20 or text_lower.count("\t") > 15
    no_tables = not has_complex_tables
    
    lines = [l.strip() for l in resume_text.split("\n") if l.strip()]
    no_long_paragraphs = all(len(l) < 800 for l in lines)
    
    items = {
        "searchable_text": searchable,
        "standard_headings": standard_headings,
        "no_complex_tables": no_tables,
        "no_long_paragraphs": no_long_paragraphs,
        "appropriate_length": 300 <= word_count <= 900
    }
    
    score = int(sum(1 for k, v in items.items() if v) / len(items) * 100)
    return {"score": score, "details": items}


def _calculate_keyword_density(resume_text: str, matched_skills: list) -> list:
    text_lower = resume_text.lower()
    density = []
    for skill in matched_skills:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        count = len(re.findall(pattern, text_lower))
        density.append({"skill": skill, "count": max(1, count)})
    return sorted(density, key=lambda x: x["count"], reverse=True)


def _section_similarity(resume_text: str, jd_text: str) -> float:
    """Whole-document semantic similarity using sentence embeddings.

    Both texts are chunked and mean-pooled into a single vector each
    (see semantic_model.embed_document), then compared with cosine
    similarity. Unlike TF-IDF this captures meaning, not just shared
    vocabulary -- e.g. a resume describing "built a recommendation engine
    with collaborative filtering" will score as related to a JD asking for
    "machine learning experience" even with zero overlapping words.
    """
    if not resume_text.strip() or not jd_text.strip():
        return 0.0

    return max(0.0, min(1.0, semantic_model.document_similarity(resume_text, jd_text)))


def _resume_quality_notes(resume_text: str) -> list:
    notes = []
    text_lower = resume_text.lower()
    word_count = len(resume_text.split())

    if word_count < 150:
        notes.append(f"<strong>Short Resume ({word_count} words)</strong>: Your resume is extremely brief. The range is 300 to 800 words.")
    elif word_count > 1000:
        notes.append(f"<strong>Long Resume ({word_count} words)</strong>: Your resume is quite long. Consider trimming it to under 800 words.")

    metrics_matches = re.findall(r"\d+%|\d+\+|\$\d+|\b\d{2,}\b", resume_text)
    metrics_count = len(metrics_matches)
    if metrics_count == 0:
        notes.append("<strong>Missing Quantifiable Impact</strong>: We couldn't find numbers or percentages. Use the <em>STAR</em> method to add numbers, e.g. <em>'improved speed by 35%'</em>.")
    elif metrics_count < 3:
        notes.append(f"<strong>Low Quantifiable Impact ({metrics_count} found)</strong>: Try to add more metrics (e.g. user growth, speed improvements, or cost reductions).")

    found_verbs = [v for v in ACTION_VERBS if f" {v}" in text_lower or f"\n{v}" in text_lower]
    if len(found_verbs) < 4:
        notes.append(f"<strong>Weak Action Verbs</strong>: Your resume doesn't use enough strong action verbs. Start bullet points with verbs like <em>'Spearheaded'</em>, <em>'Engineered'</em>, or <em>'Optimized'</em>.")

    weak_phrases_found = [p for p in ["responsible for", "assisted with", "helped to", "worked on", "duties included"] if p in text_lower]
    if weak_phrases_found:
        notes.append(f"<strong>Passive Language</strong>: You used passive phrases like {', '.join(f'\"<em>{p}</em>\"' for p in weak_phrases_found)}. Replace them with direct action statements.")

    return notes


def _compute_skill_weight(skill: str, jd_text_lower: str) -> float:
    """Derive how important a skill is *for this specific JD*, instead of
    consulting a static hand-picked importance table.

    Signals used:
    - How many times the JD mentions the skill (repeated = emphasized).
    - How early it's mentioned (job titles / must-have skills tend to be
      listed near the top; "nice to have" extras tend to trail at the end).
    - Soft skills are weighted a bit lower than technical ones, since ATS
      matching for technical roles is normally dominated by hard skills.
    """
    pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
    matches = list(re.finditer(pattern, jd_text_lower))
    count = len(matches)

    frequency_weight = 1.0 + math.log1p(count) * 2.5

    if matches and len(jd_text_lower) > 0:
        first_pos_ratio = matches[0].start() / len(jd_text_lower)
    else:
        first_pos_ratio = 1.0
    position_weight = (1.0 - first_pos_ratio) * 2.0

    weight = frequency_weight + position_weight
    if skill in SOFT_SKILLS:
        weight *= 0.6

    return max(1.0, weight)


def compute_skill_weights(jd_text: str, skills) -> dict:
    """Public wrapper around _compute_skill_weight for a set/list of skills,
    reused by the interview module so question difficulty can reflect how
    heavily *this* JD actually emphasizes each skill.
    """
    jd_text_lower = (jd_text or "").lower()
    return {skill: _compute_skill_weight(skill, jd_text_lower) for skill in skills}


def analyze_resume_vs_jd(resume_text: str, jd_text: str) -> dict:
    resume_skills = _find_skills(resume_text)
    jd_skills = _find_skills(jd_text)

    if not jd_skills:
        matched_skills = sorted(resume_skills)
        missing_skills = []
        worth_clarifying = []
        extra_skills = []
        skill_match_score = 100.0
        match_ratios = {}
        match_tiers = {}
        match_evidence = {}
        match_evidence_confident = {}
    else:
        # Calculate priorities (required vs preferred)
        skills_priority = _get_jd_skills_with_priority(jd_text, jd_skills)
        
        # Match ratios/tiers: full (1.0), cert-only (0.5), partial/semantic
        # (0.6), weak/inferred (0.3), none (0.0). "weak" means the resume
        # doesn't state the skill but contains something plausibly related
        # (e.g. Kotlin+Firebase for "Android") -- flagged separately below
        # rather than treated the same as a confirmed gap.
        match_ratios = {}
        match_tiers = {}
        match_evidence = {}
        match_evidence_confident = {}
        for jd_skill in jd_skills:
            if jd_skill in resume_skills:
                # Check for certification-only matches for cloud providers
                if jd_skill in ["azure", "aws", "gcp"] and _check_certification_only(resume_text, jd_skill):
                    match_ratios[jd_skill] = 0.5
                    match_tiers[jd_skill] = "cert_only"
                    match_evidence[jd_skill] = jd_skill
                    match_evidence_confident[jd_skill] = True
                else:
                    match_ratios[jd_skill] = 1.0
                    match_tiers[jd_skill] = "full"
                    match_evidence[jd_skill] = jd_skill
                    match_evidence_confident[jd_skill] = True
            else:
                # Before relying on the (sometimes-unavailable or too-strict)
                # semantic embedding model, check the curated implies-map:
                # does the resume contain a specific tool/practice that is
                # direct, unambiguous evidence of this broader skill? e.g.
                # resume says "Git"/"GitHub" -> counts as "version control".
                implying_tools = SKILL_IMPLIES.get(jd_skill, set())
                evidence_tool = next((t for t in implying_tools if t in resume_skills), None)
                # Related-but-not-equivalent practices (e.g. Scrum vs Agile)
                # -- checked next, ahead of the embedding fallback, since
                # this curated relationship is more reliable for these
                # specific pairs than a short-phrase embedding comparison.
                weak_related = SKILL_IMPLIES_WEAK.get(jd_skill, set())
                weak_evidence_tool = next((t for t in weak_related if t in resume_skills), None)
                if evidence_tool:
                    match_ratios[jd_skill] = 1.0
                    match_tiers[jd_skill] = "implied"
                    match_evidence[jd_skill] = evidence_tool
                    match_evidence_confident[jd_skill] = True
                elif weak_evidence_tool:
                    match_ratios[jd_skill] = WEAK_MATCH_RATIO
                    match_tiers[jd_skill] = "weak"
                    match_evidence[jd_skill] = weak_evidence_tool
                    match_evidence_confident[jd_skill] = True
                else:
                    ratio, tier, evidence, score = _check_partial_match(jd_skill, resume_skills)
                    match_ratios[jd_skill] = ratio
                    match_tiers[jd_skill] = tier
                    match_evidence[jd_skill] = evidence
                    # A score just barely over WEAK_MATCH_THRESHOLD is too
                    # thin a signal to state as a specific claimed relation
                    # (e.g. "closest thing found: problem solving" for
                    # "Time Management") -- only surface the evidence text
                    # when it clears the stronger partial-match bar.
                    match_evidence_confident[jd_skill] = score >= PARTIAL_MATCH_THRESHOLD

        matched_skills = sorted([s for s, t in match_tiers.items() if t in ("full", "cert_only", "partial", "implied")])
        worth_clarifying = sorted([s for s, t in match_tiers.items() if t == "weak"])
        missing_skills = sorted([s for s, t in match_tiers.items() if t == "none"])
        extra_skills = sorted(resume_skills - jd_skills)

        # Weighted skill scoring -- weights are derived per-JD (see
        # _compute_skill_weight) rather than looked up from a static table.
        jd_text_lower = jd_text.lower()
        skill_weights = {skill: _compute_skill_weight(skill, jd_text_lower) for skill in jd_skills}

        weighted_matched_sum = 0.0
        weighted_total_sum = 0.0
        for skill in jd_skills:
            weight = skill_weights[skill]
            # Give double weight to required skills
            adj_weight = weight * (2.0 if skills_priority[skill] == "required" else 1.0)
            weighted_matched_sum += match_ratios[skill] * adj_weight
            weighted_total_sum += adj_weight
            
        skill_match_score = (weighted_matched_sum / weighted_total_sum * 100) if weighted_total_sum > 0.0 else 100.0

    # Separate technical vs soft skills
    tech_matched = [s for s in matched_skills if s not in SOFT_SKILLS]
    soft_matched = [s for s in matched_skills if s in SOFT_SKILLS]

    # Prioritize missing skills
    critical_missing = []
    important_missing = []
    nice_to_have_missing = []
    
    if jd_skills:
        required_weights = sorted(
            skill_weights[s] for s in jd_skills if skills_priority.get(s) == "required" and s not in SOFT_SKILLS
        )
        # A skill counts as "critical" if it's in the upper third of how
        # heavily *this* JD emphasizes its required technical skills --
        # relative to this JD, not against a fixed global number.
        critical_cutoff = required_weights[int(len(required_weights) * 2 / 3)] if required_weights else 0.0

        for skill in missing_skills:
            weight = skill_weights.get(skill, _compute_skill_weight(skill, jd_text.lower()))
            priority = skills_priority.get(skill, "required")

            if skill in SOFT_SKILLS:
                nice_to_have_missing.append(skill)
            elif priority == "required":
                if weight >= critical_cutoff:
                    critical_missing.append(skill)
                else:
                    important_missing.append(skill)
            else: # preferred
                if weight >= critical_cutoff:
                    important_missing.append(skill)
                else:
                    nice_to_have_missing.append(skill)

    # Contextual/semantic similarity (sentence-embedding based)
    resume_sections = _extract_sections(resume_text)
    jd_sections = _extract_sections(jd_text)

    def _section_sim_like_for_like(name: str) -> float:
        """Compare a resume section against the *same* section of the JD,
        but only when the JD genuinely has one.

        Comparing a small, focused resume section (e.g. a few Education
        bullet points) against the JD's *entire* text -- title, location,
        unrelated responsibilities, benefits, every other section -- 
        systematically waters down even a perfect match, since most of the
        JD's full text has nothing to do with that one resume section. That
        used to happen whenever the JD lacked a same-named section, which
        for real-world JDs (that use their own headings like "Key
        Responsibilities" rather than resume-style ones) was most of the
        time -- so this component was quietly deflating the contextual
        score for the vast majority of real JDs, not just edge cases.

        So instead we only produce this signal when both sides have real
        content for the same section name; when the JD doesn't, we return
        0.0 and let it drop out of the weighted average entirely (see the
        weighting logic below, which only counts a signal when it's > 0),
        leaning on the whole-document base_semantic_sim instead -- a fair,
        undiluted comparison either way.
        """
        resume_part = resume_sections.get(name, "")
        if not resume_part:
            return 0.0
        jd_part = jd_sections.get(name, "")
        if len(jd_part.split()) < MIN_JD_SECTION_WORDS:
            return 0.0
        return _section_similarity(resume_part, jd_part)

    base_semantic_sim = _section_similarity(resume_text, jd_text)
    project_sim = _section_sim_like_for_like("projects")
    experience_sim = _section_sim_like_for_like("experience")
    education_sim = _section_sim_like_for_like("education")
    
    # Final Context Score Formula (multi-signal) - dynamically adjusting weights if sections are missing
    total_weight = 0.40
    weighted_score = 0.40 * base_semantic_sim
    
    if project_sim > 0.0:
        weighted_score += 0.30 * project_sim
        total_weight += 0.30
    
    if experience_sim > 0.0:
        weighted_score += 0.20 * experience_sim
        total_weight += 0.20
        
    if education_sim > 0.0:
        weighted_score += 0.10 * education_sim
        total_weight += 0.10
        
    # Normalize against the weights we actually used
    semantic_sim = (weighted_score / total_weight) * 100.0
    # Overall Score Formula: 70% Skills Match, 30% Contextual/Semantic Similarity
    overall_score = round(0.70 * skill_match_score + 0.30 * semantic_sim, 1)
    overall_score = max(0.0, min(100.0, overall_score))

    # Keyword density
    keyword_density = _calculate_keyword_density(resume_text, matched_skills)

    # ATS Compatibility
    ats_comp = _check_ats_compatibility(resume_text)

    # Contextual Quality notes (Point 10)
    quality_notes = _resume_quality_notes(resume_text)

    # Suggestions for critical missing skills. This is intentionally generic
    # (no per-skill special-casing like "if skill == 'kubernetes'") so it
    # works for any skill in the vocabulary, not just a hand-picked list.
    for skill in critical_missing[:3]:
        display = skill.upper() if len(skill) <= 4 else skill.title()
        quality_notes.append(
            f"<strong>Add {display} experience</strong>: This job description emphasizes "
            f"{display} but it doesn't appear in your resume. Add specific, concrete context "
            f"(a project, task, or achievement) where you actually used or studied it."
        )

    for skill, ratio in match_ratios.items():
        if ratio == 0.5:  # certification-only mention, no hands-on evidence
            display = skill.upper() if len(skill) <= 4 else skill.title()
            quality_notes.append(
                f"<strong>Describe hands-on {display} work</strong>: {display} currently only "
                f"appears in a certification/coursework context. Describe actual hands-on work "
                f"(a deployment, project, or task) to show practical experience, not just a credential."
            )

    for skill in worth_clarifying:
        display = skill.upper() if len(skill) <= 4 else skill.title()
        evidence = match_evidence.get(skill)
        show_evidence = evidence and match_evidence_confident.get(skill)
        evidence_note = f' (closest thing found: "{evidence}")' if show_evidence else ""
        quality_notes.append(
            f"<strong>Consider stating {display} explicitly</strong>: your resume doesn't say "
            f"{display} directly, but contains something related{evidence_note}. If you actually "
            f"have this skill, spell it out explicitly so ATS systems and reviewers don't have to guess."
        )

    return {
        "overall_score": overall_score,
        "skill_coverage": round(skill_match_score, 1),
        "tfidf_similarity": round(semantic_sim, 1),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "worth_clarifying": worth_clarifying,
        "extra_skills": extra_skills,
        "weaknesses": missing_skills,
        "quality_notes": quality_notes,
        "technical_matched": tech_matched,
        "soft_matched": soft_matched,
        "critical_missing": critical_missing,
        "important_missing": important_missing,
        "nice_to_have_missing": nice_to_have_missing,
        "keyword_density": keyword_density,
        "ats_compatibility": ats_comp,
        "score_breakdown": {
            "skill_match": round(skill_match_score, 1),
            "semantic_match": round(semantic_sim, 1)
        }
    }
