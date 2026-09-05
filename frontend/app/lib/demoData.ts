/**
 * Fabricated but internally-consistent demo dataset.
 *
 * Every number here is hand-authored so that totals, averages, and
 * percentages are all derivable from the same underlying scores -- nothing
 * downstream (`repository.ts`) invents a separate "summary" number that
 * isn't computed from these arrays. This is sample data for a Wednesday
 * academic-project review, not live production data; every screen that
 * reads it is required to show a "Demo data" label (see `ui/DemoBadge.tsx`).
 */

import type {
  Assessment,
  COAttainment,
  COPOLink,
  Faculty,
  POAttainment,
  Question,
  Student,
  Subject,
  Submission,
} from "./domain";

export const FACULTY: Faculty = {
  id: "fac-1",
  name: "Dr. Rajesh Kumar",
  title: "Associate Professor, Computer Engineering",
  subjectIds: ["sub-nlp", "sub-bc", "sub-ml", "sub-bda", "sub-mis"],
};

export const SUBJECTS: Subject[] = [
  { id: "sub-nlp", code: "CS601", name: "Natural Language Processing", facultyId: "fac-1", coCode: "CO1" },
  { id: "sub-bc", code: "CS602", name: "Blockchain", facultyId: "fac-1", coCode: "CO2" },
  { id: "sub-ml", code: "CS603", name: "Machine Learning", facultyId: "fac-1", coCode: "CO3" },
  { id: "sub-bda", code: "CS604", name: "Big Data Analytics", facultyId: "fac-1", coCode: "CO4" },
  { id: "sub-mis", code: "CS605", name: "Management Information Systems", facultyId: "fac-1", coCode: "CO5" },
];

const ALL_SUBJECT_IDS = SUBJECTS.map((s) => s.id);

export const STUDENTS: Student[] = [
  { id: "st-1", name: "Aarav Sharma", rollNumber: "21CE001", subjectIds: ALL_SUBJECT_IDS },
  { id: "st-2", name: "Priya Nair", rollNumber: "21CE002", subjectIds: ALL_SUBJECT_IDS },
  { id: "st-3", name: "Rohan Verma", rollNumber: "21CE003", subjectIds: ALL_SUBJECT_IDS },
  { id: "st-4", name: "Sneha Patil", rollNumber: "21CE004", subjectIds: ALL_SUBJECT_IDS },
  { id: "st-5", name: "Kabir Singh", rollNumber: "21CE005", subjectIds: ALL_SUBJECT_IDS },
  { id: "st-6", name: "Ananya Iyer", rollNumber: "21CE006", subjectIds: ALL_SUBJECT_IDS },
];

/** The fixed demo identity used by the Student portal (there is no login yet). */
export const DEMO_STUDENT_ID = "st-1";

function q(
  id: string,
  text: string,
  modelAnswer: string,
  maxScore: number,
  topic: string,
): Question {
  return {
    id,
    text,
    modelAnswer,
    maxScore,
    topic,
    criteria: [
      { name: "Concept", maxScore: Math.round(maxScore * 0.4 * 10) / 10 },
      { name: "Accuracy", maxScore: Math.round(maxScore * 0.3 * 10) / 10 },
      { name: "Precision", maxScore: Math.round(maxScore * 0.2 * 10) / 10 },
      { name: "Terminology", maxScore: Math.round(maxScore * 0.1 * 10) / 10 },
    ],
  };
}

export const ASSESSMENTS: Assessment[] = [
  {
    id: "a-nlp-tt1",
    title: "NLP — TT1",
    subjectId: "sub-nlp",
    date: "2026-08-12",
    totalMarks: 20,
    status: "published",
    source: "demo",
    questions: [
      q("Q1", "Explain Named Entity Recognition (NER) with an example.", "NER locates and classifies named entities (person, organisation, location, ...) in text.", 10, "Named Entity Recognition"),
      q("Q2", "What is lemmatization? How does it differ from stemming?", "Lemmatization reduces a word to its dictionary base form using vocabulary and morphology, unlike stemming's crude suffix-stripping.", 10, "Lemmatization"),
    ],
  },
  {
    id: "a-nlp-tt2",
    title: "NLP — TT2",
    subjectId: "sub-nlp",
    date: "2026-09-02",
    totalMarks: 20,
    status: "published",
    source: "demo",
    questions: [
      q("Q1", "Describe syntax analysis (parsing) in an NLP pipeline.", "Syntax analysis assigns a grammatical structure (parse tree) to a sentence based on a formal grammar.", 10, "Syntax Analysis"),
      q("Q2", "What does a dependency parser produce, and how does it differ from a constituency parser?", "A dependency parser produces head-dependent relations between words rather than nested phrase structure.", 10, "Dependency Parsing"),
    ],
  },
  {
    id: "a-bc-assign1",
    title: "Blockchain — Assignment 1",
    subjectId: "sub-bc",
    date: "2026-08-20",
    totalMarks: 15,
    status: "published",
    source: "demo",
    questions: [
      q("Q1", "Compare Proof of Work and Proof of Stake consensus mechanisms.", "PoW relies on computational effort; PoS relies on staked capital, trading energy cost for capital-at-risk.", 15, "Consensus Mechanisms"),
    ],
  },
  {
    id: "a-ml-assign1",
    title: "ML — Assignment 1",
    subjectId: "sub-ml",
    date: "2026-08-28",
    totalMarks: 20,
    status: "published",
    source: "demo",
    questions: [
      q("Q1", "Explain the bias-variance tradeoff.", "High bias underfits; high variance overfits. Model capacity and regularisation trade one against the other.", 10, "Bias-Variance Tradeoff"),
      q("Q2", "Describe how gradient descent updates model parameters.", "Parameters move opposite the loss gradient, scaled by a learning rate, until convergence.", 10, "Gradient Descent"),
    ],
  },
  {
    id: "a-bda-quiz1",
    title: "Big Data Analytics — Quiz 1",
    subjectId: "sub-bda",
    date: "2026-08-25",
    totalMarks: 10,
    status: "published",
    source: "demo",
    questions: [
      q("Q1", "Explain the MapReduce programming model.", "MapReduce splits work into a map phase (transform) and a reduce phase (aggregate) across a distributed cluster.", 10, "MapReduce"),
    ],
  },
  {
    id: "a-mis-tt1",
    title: "MIS — TT1",
    subjectId: "sub-mis",
    date: "2026-09-18",
    totalMarks: 20,
    status: "draft",
    source: "demo",
    questions: [
      q("Q1", "What is the role of an MIS in organisational decision-making?", "An MIS aggregates operational data into reports that support tactical and strategic decisions.", 10, "Decision Support"),
      q("Q2", "Differentiate between MIS and a Decision Support System (DSS).", "MIS reports structured, routine information; a DSS supports semi-structured/unstructured, ad-hoc decisions.", 10, "MIS vs DSS"),
    ],
  },
];

function result(
  questionId: string,
  score: number,
  maxScore: number,
  strengths: string[],
  missingConcepts: string[],
  feedback: string,
  studentAnswer: string,
  confidence = 0.88,
  ocrConfidence = 0.9,
) {
  const combined = Math.round(confidence * (0.5 + 0.5 * ocrConfidence) * 10000) / 10000;
  return {
    questionId,
    score,
    maxScore,
    conceptScore: Math.round(score * 0.4 * 10) / 10,
    accuracyScore: Math.round(score * 0.3 * 10) / 10,
    precisionScore: Math.round(score * 0.2 * 10) / 10,
    technicalTerminologyScore: Math.round(score * 0.1 * 10) / 10,
    strengths,
    missingConcepts,
    feedback,
    confidence,
    ocrConfidence,
    combinedConfidence: combined,
    needsReview: combined < 0.6,
    answerDetected: true,
    studentAnswer,
  };
}

let submissionSeq = 0;
function submission(
  assessmentId: string,
  studentId: string,
  results: ReturnType<typeof result>[] | null,
): Submission {
  submissionSeq += 1;
  if (!results) {
    return {
      id: `sub-${submissionSeq}`,
      assessmentId,
      studentId,
      status: "pending",
      results: [],
      totalScore: 0,
      totalMaxScore: ASSESSMENTS.find((a) => a.id === assessmentId)!.totalMarks,
      overallConfidence: 0,
      needsReview: false,
      evaluatedAt: null,
      source: "demo",
    };
  }
  const totalScore = Math.round(results.reduce((s, r) => s + r.score, 0) * 10) / 10;
  const totalMaxScore = results.reduce((s, r) => s + r.maxScore, 0);
  const overallConfidence =
    Math.round((results.reduce((s, r) => s + r.combinedConfidence, 0) / results.length) * 10000) / 10000;
  return {
    id: `sub-${submissionSeq}`,
    assessmentId,
    studentId,
    status: "evaluated",
    results,
    totalScore,
    totalMaxScore,
    overallConfidence,
    needsReview: results.some((r) => r.needsReview),
    evaluatedAt: "2026-08-14T10:30:00Z",
    source: "demo",
  };
}

export const SUBMISSIONS: Submission[] = [
  // NLP TT1 — Aarav's 16/20 is the featured walkthrough example.
  submission("a-nlp-tt1", "st-1", [
    result("Q1", 6.5, 10, ["Correctly identifies entity categories"], ["No worked example given"], "Definition is correct but the example is missing — add a labelled sentence next time.", "NER identifies names of people, organisations and places in text."),
    result("Q2", 9.5, 10, ["Clear contrast with stemming", "Correct terminology"], [], "Strong, precise answer.", "Lemmatization uses a dictionary and morphology to return the base form, e.g. 'better' -> 'good', unlike stemming which just chops suffixes."),
  ]),
  submission("a-nlp-tt1", "st-2", [
    result("Q1", 8, 10, ["Good example given"], ["Could mention entity types more explicitly"], "Solid, mostly complete.", "NER finds names like 'Barack Obama' or 'Paris' and tags what type they are."),
    result("Q2", 8, 10, ["Correct core distinction"], [], "Good answer.", "Lemmatization gives the dictionary form; stemming just cuts the ending off."),
  ]),
  submission("a-nlp-tt1", "st-3", [
    result("Q1", 5, 10, [], ["Missing example", "Vague on entity categories"], "Definition is too generic — review the categories (PERSON, ORG, GPE, ...).", "NER is used to find important words in a sentence."),
    result("Q2", 6, 10, ["Attempts a distinction"], ["Distinction is imprecise"], "Re-check the difference between rule-based stemming and dictionary-based lemmatization.", "Lemmatization and stemming both shorten words to their root."),
  ]),
  submission("a-nlp-tt1", "st-4", [
    result("Q1", 9, 10, ["Precise definition", "Good example"], [], "Excellent.", "NER classifies spans of text into categories like PERSON, ORG and GPE, e.g. 'Google' -> ORG."),
    result("Q2", 9.5, 10, ["Textbook-accurate"], [], "Excellent.", "Lemmatization returns the dictionary base form using morphological analysis; stemming is a heuristic suffix-stripping process."),
  ]),
  submission("a-nlp-tt1", "st-5", [
    result("Q1", 4, 10, [], ["No definition of entity types", "No example"], "Needs a clearer definition and an example.", "NER is a part of NLP."),
    result("Q2", 5, 10, [], ["Distinction not made"], "The difference from stemming is not addressed.", "Lemmatization is reducing words."),
  ]),
  submission("a-nlp-tt1", "st-6", null), // not yet submitted

  // NLP TT2
  submission("a-nlp-tt2", "st-1", [
    result("Q1", 4, 10, ["Mentions parse trees"], ["Grammar formalism not explained", "No example tree"], "Review formal grammars (e.g. context-free grammar) and include a worked parse tree.", "Syntax analysis builds a tree from the sentence."),
    result("Q2", 7.5, 10, ["Correct head-dependent framing"], ["Could contrast with constituency trees more directly"], "Good understanding, tighten the comparison.", "A dependency parser links words by grammatical relation rather than building nested phrases."),
  ]),
  submission("a-nlp-tt2", "st-2", [
    result("Q1", 7, 10, ["Correct grammar reference"], ["Example tree missing"], "Good, add an example next time.", "Syntax analysis uses a context-free grammar to assign structure to a sentence."),
    result("Q2", 8, 10, ["Clear contrast given"], [], "Well explained.", "Dependency parsing gives head-dependent links; constituency parsing gives nested phrase brackets."),
  ]),
  submission("a-nlp-tt2", "st-4", [
    result("Q1", 8.5, 10, ["Clear, example included"], [], "Very good.", "Syntax analysis parses the sentence into a tree using a context-free grammar, e.g. S -> NP VP."),
    result("Q2", 9, 10, ["Precise and complete"], [], "Excellent.", "Dependency parsing produces head-dependent arcs; constituency parsing produces nested constituents like NP and VP."),
  ]),

  // Blockchain — Assignment 1
  submission("a-bc-assign1", "st-1", [result("Q1", 11, 15, ["Correct core mechanisms"], ["Energy cost of PoW not quantified"], "Good comparison, add the energy-cost angle.", "PoW uses computational puzzles; PoS uses staked coins to select validators.")]),
  submission("a-bc-assign1", "st-2", [result("Q1", 13, 15, ["Thorough", "Mentions Nakamoto"], [], "Very good.", "PoW requires solving a hash puzzle (Bitcoin); PoS selects validators by stake, reducing energy use.")]),
  submission("a-bc-assign1", "st-3", [result("Q1", 9, 15, [], ["Missing tradeoffs", "No named examples"], "Add concrete examples (Bitcoin vs Ethereum post-merge).", "PoW and PoS are both ways to agree on the blockchain.")]),
  submission("a-bc-assign1", "st-4", [result("Q1", 14, 15, ["Excellent depth"], [], "Excellent.", "PoW: miners compete on hash puzzles, energy-intensive, security via computation. PoS: validators stake capital, energy-efficient, security via economic risk.")]),
  submission("a-bc-assign1", "st-5", [result("Q1", 7, 15, [], ["Definitions incomplete"], "Review both mechanisms from the lecture notes.", "Proof of work needs mining, proof of stake needs staking.")]),
  submission("a-bc-assign1", "st-6", null),

  // ML — Assignment 1 (deliberately partial -> real "pending reviews")
  submission("a-ml-assign1", "st-1", [
    result("Q1", 7, 10, ["Correct framing"], ["No diagram/curve described"], "Good, describe the error curves next time.", "High bias means underfitting; high variance means overfitting."),
    result("Q2", 8, 10, ["Correct update rule"], [], "Good.", "Gradient descent updates weights by subtracting the learning rate times the gradient of the loss."),
  ]),
  submission("a-ml-assign1", "st-2", [
    result("Q1", 9, 10, ["Clear, textbook-accurate"], [], "Excellent.", "Bias-variance tradeoff: simple models underfit (high bias), complex models overfit (high variance); total error is minimised at a sweet spot."),
    result("Q2", 9, 10, ["Complete"], [], "Excellent.", "Gradient descent iteratively updates parameters opposite the gradient direction, scaled by the learning rate, until the loss converges."),
  ]),
  submission("a-ml-assign1", "st-3", null),
  submission("a-ml-assign1", "st-4", null),
  submission("a-ml-assign1", "st-5", null),
  submission("a-ml-assign1", "st-6", null),

  // Big Data Analytics — Quiz 1 (full class participation)
  submission("a-bda-quiz1", "st-1", [result("Q1", 8, 10, ["Correct map/reduce split"], [], "Good.", "MapReduce splits data across a map phase and combines results in a reduce phase.")]),
  submission("a-bda-quiz1", "st-2", [result("Q1", 9, 10, ["Precise"], [], "Very good.", "The map phase transforms key-value pairs; the reduce phase aggregates them across the cluster.")]),
  submission("a-bda-quiz1", "st-3", [result("Q1", 6, 10, [], ["Reduce phase unclear"], "Clarify what happens during the reduce phase.", "MapReduce processes big data using mappers.")]),
  submission("a-bda-quiz1", "st-4", [result("Q1", 9.5, 10, ["Excellent depth"], [], "Excellent.", "MapReduce distributes a map function across data shards, then a reduce function aggregates intermediate results.")]),
  submission("a-bda-quiz1", "st-5", [result("Q1", 5, 10, [], ["Vague on both phases"], "Revisit the MapReduce lecture — both phases need clearer definitions.", "MapReduce is for processing large datasets.")]),
  submission("a-bda-quiz1", "st-6", [result("Q1", 7, 10, ["Reasonable understanding"], ["Missing distributed-cluster context"], "Good start, connect it to cluster-scale processing.", "Map processes data, reduce combines the output.")]),
];

// ---------------------------------------------------------------------------
// CO / PO demo mapping. Kept intentionally simple and transparent (see
// repository.ts for the attainment formula) rather than a black-box score --
// this is explicitly a demo illustration of the OBE surface, not a claim
// that full OBE automation is implemented (it isn't; see the roadmap page).
// ---------------------------------------------------------------------------

export const CO_DEFINITIONS: Omit<COAttainment, "achievedPercent">[] = [
  { code: "CO1", description: "Apply NLP techniques to analyse and process natural language text.", targetPercent: 70, subjectId: "sub-nlp" },
  { code: "CO2", description: "Evaluate blockchain consensus mechanisms and their tradeoffs.", targetPercent: 70, subjectId: "sub-bc" },
  { code: "CO3", description: "Apply core machine learning concepts to model bias/variance and optimisation.", targetPercent: 70, subjectId: "sub-ml" },
  { code: "CO4", description: "Explain distributed data-processing paradigms for large-scale analytics.", targetPercent: 65, subjectId: "sub-bda" },
  { code: "CO5", description: "Analyse the role of information systems in organisational decision-making.", targetPercent: 65, subjectId: "sub-mis" },
];

export const PO_DEFINITIONS: POAttainment[] = [
  { code: "PO1", description: "Engineering knowledge" },
  { code: "PO2", description: "Problem analysis" },
  { code: "PO5", description: "Modern tool usage" },
  { code: "PO12", description: "Life-long learning" },
];

export const CO_PO_LINKS: COPOLink[] = [
  { coCode: "CO1", poCode: "PO1", weight: 2 },
  { coCode: "CO1", poCode: "PO2", weight: 3 },
  { coCode: "CO1", poCode: "PO5", weight: 2 },
  { coCode: "CO2", poCode: "PO1", weight: 2 },
  { coCode: "CO2", poCode: "PO2", weight: 2 },
  { coCode: "CO2", poCode: "PO12", weight: 1 },
  { coCode: "CO3", poCode: "PO1", weight: 3 },
  { coCode: "CO3", poCode: "PO2", weight: 3 },
  { coCode: "CO3", poCode: "PO5", weight: 3 },
  { coCode: "CO4", poCode: "PO2", weight: 2 },
  { coCode: "CO4", poCode: "PO5", weight: 3 },
  { coCode: "CO5", poCode: "PO1", weight: 1 },
  { coCode: "CO5", poCode: "PO12", weight: 2 },
];
