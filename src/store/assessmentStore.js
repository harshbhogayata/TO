/**
 * src/store/assessmentStore.js
 * Zustand store for assessments / quiz engine state.
 */
import { create } from 'zustand';

export const useAssessmentStore = create((set, get) => ({
    // ── Catalog ──────────────────────────────────────────────────────────────
    assessments: [],
    assessmentsLoading: false,
    assessmentsError: null,
    filters: {
        search: '',
        type: '',
        difficulty: '',
        skill: '',
    },

    setAssessments: (assessments) => set({ assessments }),
    setAssessmentsLoading: (loading) => set({ assessmentsLoading: loading }),
    setAssessmentsError: (error) => set({ assessmentsError: error }),
    setFilter: (key, value) =>
        set((state) => ({ filters: { ...state.filters, [key]: value } })),
    resetFilters: () =>
        set({
            filters: { search: '', type: '', difficulty: '', skill: '' },
        }),

    // ── Active assessment detail ─────────────────────────────────────────────
    activeAssessment: null,
    setActiveAssessment: (assessment) => set({ activeAssessment: assessment }),

    // ── Live attempt (player) ────────────────────────────────────────────────
    attempt: null,
    currentQuestionIndex: 0,
    answers: {},      // { questionId: { selectedOption, code, ... } }
    flagged: {},      // { questionId: true }
    timeRemaining: 0,

    setAttempt: (attempt) => set({ attempt }),
    setCurrentQuestionIndex: (index) => set({ currentQuestionIndex: index }),
    setAnswer: (questionId, answer) =>
        set((state) => ({
            answers: { ...state.answers, [questionId]: answer },
        })),
    toggleFlag: (questionId) =>
        set((state) => ({
            flagged: {
                ...state.flagged,
                [questionId]: !state.flagged[questionId],
            },
        })),
    setTimeRemaining: (seconds) => set({ timeRemaining: seconds }),
    resetAttempt: () =>
        set({
            attempt: null,
            currentQuestionIndex: 0,
            answers: {},
            flagged: {},
            timeRemaining: 0,
        }),

    // ── Results ──────────────────────────────────────────────────────────────
    activeResult: null,
    myResults: [],
    setActiveResult: (result) => set({ activeResult: result }),
    setMyResults: (results) => set({ myResults: results }),

    // ── Skill Badges ─────────────────────────────────────────────────────────
    badges: [],
    setBadges: (badges) => set({ badges }),

    // ── Invitations ──────────────────────────────────────────────────────────
    invitations: [],
    setInvitations: (invitations) => set({ invitations }),

    // ── Company dashboard ────────────────────────────────────────────────────
    companyAssessments: [],
    companyResults: [],
    setCompanyAssessments: (data) => set({ companyAssessments: data }),
    setCompanyResults: (data) => set({ companyResults: data }),

    // ── Question Banks ───────────────────────────────────────────────────────
    questionBanks: [],
    questionBanksLoading: false,
    questionBanksError: null,
    activeBank: null,
    bankQuestions: [],
    bankQuestionsLoading: false,
    approvalQueue: [],

    setQuestionBanks: (banks) => set({ questionBanks: banks }),
    setQuestionBanksLoading: (loading) => set({ questionBanksLoading: loading }),
    setQuestionBanksError: (error) => set({ questionBanksError: error }),
    setActiveBank: (bank) => set({ activeBank: bank }),
    setBankQuestions: (questions) => set({ bankQuestions: questions }),
    setBankQuestionsLoading: (loading) => set({ bankQuestionsLoading: loading }),
    setApprovalQueue: (queue) => set({ approvalQueue: queue }),
}));
