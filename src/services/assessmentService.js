/**
 * src/services/assessmentService.js
 * API service for the Assessment Engine module.
 * Maps to backend endpoints under /api/v1/assessments/
 */
import api from './api';

const resolveAttemptId = (primary, secondary) => secondary ?? primary;
const resolvePayload = (secondary, tertiary) => tertiary ?? secondary ?? {};

const assessmentService = {
    listAssessments: (params) => api.get('/assessments/', { params }),
    getAssessment: (id) => api.get(`/assessments/${id}/`),

    startAttempt: (assessmentId) =>
        api.post(`/assessments/${assessmentId}/start/`),
    getAttempt: (assessmentIdOrAttemptId, attemptId) =>
        api.get(`/assessments/attempts/${resolveAttemptId(assessmentIdOrAttemptId, attemptId)}/`),
    submitAnswer: (assessmentIdOrAttemptId, attemptIdOrData, maybeData) => {
        const attemptId = resolveAttemptId(assessmentIdOrAttemptId, maybeData ? attemptIdOrData : undefined);
        const data = resolvePayload(attemptIdOrData, maybeData);
        return api.post(`/assessments/attempts/${attemptId}/answer/`, data);
    },
    finalSubmit: (assessmentIdOrAttemptId, attemptId) =>
        api.post(`/assessments/attempts/${resolveAttemptId(assessmentIdOrAttemptId, attemptId)}/submit/`),

    getResult: (assessmentIdOrAttemptId, attemptId) =>
        api.get(`/assessments/attempts/${resolveAttemptId(assessmentIdOrAttemptId, attemptId)}/result/`),
    myResults: (params) =>
        api.get('/assessments/my-results/', { params }),

    myInvitations: () => api.get('/assessments/invitations/'),
    acceptInvitation: (token) =>
        api.post(`/assessments/invitations/${token}/accept/`),
    declineInvitation: (token) =>
        api.post(`/assessments/invitations/${token}/decline/`),

    myBadges: (params) => api.get('/assessments/badges/', { params }),
    verifyBadge: (badgeId) => api.get(`/assessments/badges/verify/${badgeId}/`),

    reportProctorEvent: (assessmentIdOrAttemptId, attemptIdOrData, maybeData) => {
        const attemptId = resolveAttemptId(assessmentIdOrAttemptId, maybeData ? attemptIdOrData : undefined);
        const data = resolvePayload(attemptIdOrData, maybeData);
        return api.post(`/assessments/attempts/${attemptId}/proctor-event/`, data);
    },

    companyAssessments: (params) =>
        api.get('/assessments/company/', { params }),
    createAssessment: (data) =>
        api.post('/assessments/company/', data),
    updateAssessment: (id, data) =>
        api.patch(`/assessments/company/${id}/`, data),
    sendInvitation: (data) =>
        api.post('/assessments/invitations/send/', data),
    companyResults: (params) =>
        api.get('/assessments/company/results/', { params }),
    exportResults: (params) =>
        api.get('/assessments/company/results/export/', {
            params,
            responseType: 'blob',
        }),

    listQuestionBanks: (params) =>
        api.get('/assessments/question-banks/', { params }),
    createQuestionBank: (data) =>
        api.post('/assessments/question-banks/create/', data),
    getQuestionBank: (id) =>
        api.get(`/assessments/question-banks/${id}/`),
    updateQuestionBank: (id, data) =>
        api.patch(`/assessments/question-banks/${id}/`, data),
    deleteQuestionBank: (id) =>
        api.delete(`/assessments/question-banks/${id}/`),

    listQuestions: (bankId, params) =>
        api.get(`/assessments/question-banks/${bankId}/questions/`, { params }),
    createQuestion: (bankId, data) =>
        api.post(`/assessments/question-banks/${bankId}/questions/create/`, data),
    getQuestion: (id) =>
        api.get(`/assessments/questions/${id}/`),
    updateQuestion: (id, data) =>
        api.patch(`/assessments/questions/${id}/`, data),
    deleteQuestion: (id) =>
        api.delete(`/assessments/questions/${id}/`),
    approveQuestion: (id) =>
        api.post(`/assessments/questions/${id}/approve/`),
    bulkApproveQuestions: (questionIds) =>
        api.post('/assessments/questions/bulk-approve/', { question_ids: questionIds }),

    listTags: (params) =>
        api.get('/assessments/tags/', { params }),
};

export default assessmentService;
