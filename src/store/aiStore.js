/**
 * src/store/aiStore.js
 * Zustand store for AI/ML features: Job Writer, Interview Scheduler, Chatbot, Compensation.
 */
import { create } from 'zustand';
import { intelligenceService, getApiErrorMessage } from '../services/api';

export const useAIStore = create((set) => ({
    // ── AI Job Writer ──────────────────────────────────────────────────────
    generatedJD: null,
    jdLoading: false,
    jdError: null,
    generateJobDescription: async (data) => {
        set({ jdLoading: true, jdError: null });
        try {
            const { data: result } = await intelligenceService.generateJobDescription(data);
            set({ generatedJD: result, jdLoading: false });
            return result;
        } catch (err) {
            const msg = getApiErrorMessage(err, 'Failed to generate job description.');
            set({ jdLoading: false, jdError: msg });
            throw err;
        }
    },
    clearGeneratedJD: () => set({ generatedJD: null, jdError: null }),

    // ── Interview Scheduler ────────────────────────────────────────────────
    interviewSlots: [],
    slotsLoading: false,
    slotsError: null,
    fetchInterviewSlots: async (data) => {
        set({ slotsLoading: true, slotsError: null });
        try {
            const { data: result } = await intelligenceService.scheduleInterviews(data);
            set({ interviewSlots: result.slots || result, slotsLoading: false });
        } catch (err) {
            const msg = getApiErrorMessage(err, 'Failed to fetch interview slots.');
            set({ slotsLoading: false, slotsError: msg });
            throw err;
        }
    },

    // ── AI Chatbot ─────────────────────────────────────────────────────────
    chatHistory: [],
    chatLoading: false,
    sendChatMessage: async (message) => {
        const userMsg = { role: 'user', content: message, timestamp: Date.now() };
        set((state) => ({
            chatHistory: [...state.chatHistory, userMsg],
            chatLoading: true,
        }));
        try {
            const { data } = await intelligenceService.chatWithAI(message, {});
            const assistantMsg = {
                role: 'assistant',
                content: data.reply || data.message || data.content || '',
                timestamp: Date.now(),
            };
            set((state) => ({
                chatHistory: [...state.chatHistory, assistantMsg],
                chatLoading: false,
            }));
        } catch {
            const errorMsg = {
                role: 'error',
                content: 'Failed to get a response. Please try again.',
                timestamp: Date.now(),
            };
            set((state) => ({
                chatHistory: [...state.chatHistory, errorMsg],
                chatLoading: false,
            }));
        }
    },
    clearChat: () => set({ chatHistory: [], chatLoading: false }),

    // ── Compensation Benchmark ─────────────────────────────────────────────
    compensationData: null,
    compensationLoading: false,
    compensationError: null,
    fetchCompensation: async (role, location) => {
        set({ compensationLoading: true, compensationError: null });
        try {
            const { data } = await intelligenceService.getCompensationBenchmark(role, location);
            set({ compensationData: data, compensationLoading: false });
        } catch (err) {
            const msg = getApiErrorMessage(err, 'Failed to fetch compensation data.');
            set({ compensationLoading: false, compensationError: msg });
            throw err;
        }
    },
    clearCompensation: () => set({ compensationData: null, compensationError: null }),
}));
