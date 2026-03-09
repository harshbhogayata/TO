/**
 * src/store/assessmentStore.js
 * Zustand store for assessments / quiz engine state.
 */
import { create } from 'zustand';

const nextAttemptState = (attempt = null) => ({
    attempt,
    answers: attempt?.answers ?? {},
    flagged: Object.fromEntries((attempt?.flagged ?? []).map((questionId) => [String(questionId), true])),
    timeRemaining: attempt?.timeRemaining ?? 0,
});

export const useAssessmentStore = create((set) => ({
    assessments: [],
    assessmentsLoading: false,
    assessmentsError: null,
    filters: {
        search: '',
        type: '',
        difficulty: '',
        skill: '',
        sort: 'newest',
    },

    setAssessments: (assessments) => set({ assessments }),
    setAssessmentsLoading: (loading) => set({ assessmentsLoading: loading }),
    setAssessmentsError: (error) => set({ assessmentsError: error }),
    setFilter: (key, value) =>
        set((state) => ({ filters: { ...state.filters, [key]: value } })),
    resetFilters: () =>
        set({
            filters: { search: '', type: '', difficulty: '', skill: '', sort: 'newest' },
        }),

    activeAssessment: null,
    setActiveAssessment: (assessment) => set({ activeAssessment: assessment }),

    attempt: null,
    currentQuestionIndex: 0,
    answers: {},
    flagged: {},
    timeRemaining: 0,

    setAttempt: (attempt) => set(() => nextAttemptState(attempt)),
    setCurrentQuestionIndex: (index) => set({ currentQuestionIndex: index }),
    setAnswer: (questionId, answer) =>
        set((state) => {
            const nextAnswers = {
                ...(state.attempt?.answers ?? state.answers),
                [String(questionId)]: answer,
            };

            return {
                answers: nextAnswers,
                attempt: state.attempt ? { ...state.attempt, answers: nextAnswers } : state.attempt,
            };
        }),
    toggleFlag: (questionId) =>
        set((state) => {
            const key = String(questionId);
            const currentFlags = {
                ...(state.attempt?.flagged
                    ? Object.fromEntries(state.attempt.flagged.map((id) => [String(id), true]))
                    : state.flagged),
            };
            currentFlags[key] = !currentFlags[key];
            const flaggedIds = Object.entries(currentFlags)
                .filter(([, isFlagged]) => Boolean(isFlagged))
                .map(([id]) => id);

            return {
                flagged: currentFlags,
                attempt: state.attempt ? { ...state.attempt, flagged: flaggedIds } : state.attempt,
            };
        }),
    setTimeRemaining: (valueOrUpdater) =>
        set((state) => {
            const previous = state.attempt?.timeRemaining ?? state.timeRemaining ?? 0;
            const next = typeof valueOrUpdater === 'function'
                ? valueOrUpdater(previous)
                : valueOrUpdater;

            return {
                timeRemaining: next,
                attempt: state.attempt ? { ...state.attempt, timeRemaining: next } : state.attempt,
            };
        }),
    resetAttempt: () =>
        set({
            attempt: null,
            currentQuestionIndex: 0,
            answers: {},
            flagged: {},
            timeRemaining: 0,
        }),

    activeResult: null,
    myResults: [],
    setActiveResult: (result) => set({ activeResult: result }),
    setMyResults: (results) => set({ myResults: results }),

    badges: [],
    setBadges: (badges) => set({ badges }),

    invitations: [],
    setInvitations: (invitations) => set({ invitations }),

    companyAssessments: [],
    companyResults: [],
    setCompanyAssessments: (data) => set({ companyAssessments: data }),
    setCompanyResults: (data) => set({ companyResults: data }),

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
