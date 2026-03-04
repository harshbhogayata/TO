/**
 * src/utils/schemas.js
 * Zod validation schemas for all form inputs across the 14 new pages.
 * Every form submission MUST validate through these schemas before calling the API.
 */
import { z } from 'zod';

// ── SubscriptionPlans — plan selection ─────────────────────────────────────
export const planSelectionSchema = z.object({
    planId: z.string().min(1, 'Plan is required'),
    interval: z.enum(['monthly', 'annual'], { message: 'Select monthly or annual' }),
    couponCode: z.string().max(50).optional(),
});

// ── ReferralProgram — create referral ──────────────────────────────────────
export const referralSchema = z.object({
    refereeEmail: z
        .string()
        .email('Please enter a valid email address')
        .max(255),
});

// ── SponsoredPosts — boost campaign form ───────────────────────────────────
export const boostCampaignSchema = z.object({
    jobId: z.string().min(1, 'Select a job to sponsor'),
    dailyBudget: z
        .number({ invalid_type_error: 'Budget must be a number' })
        .min(1, 'Minimum budget is $1/day')
        .max(10000, 'Maximum budget is $10,000/day'),
    durationDays: z
        .number({ invalid_type_error: 'Duration must be a number' })
        .int('Duration must be a whole number')
        .min(1, 'Minimum 1 day')
        .max(90, 'Maximum 90 days'),
    targetAudience: z.string().min(1, 'Target audience is required').max(255),
});

// ── CRMPipeline — move candidate ───────────────────────────────────────────
export const moveCandidateSchema = z.object({
    candidateId: z.string().min(1, 'Candidate is required'),
    stageId: z.string().min(1, 'Stage is required'),
});

// ── AIJobWriter — generate JD ──────────────────────────────────────────────
export const jobDescriptionSchema = z.object({
    title: z
        .string()
        .min(2, 'Role title must be at least 2 characters')
        .max(200)
        .trim(),
    company: z.string().min(1, 'Company name is required').max(200).trim(),
    location: z.string().min(1, 'Location is required').max(200).trim(),
    type: z.string().min(1, 'Job type is required'),
    salary: z.string().optional(),
    description: z
        .string()
        .min(10, 'Description must be at least 10 characters')
        .max(5000)
        .trim(),
    requirements: z.string().max(5000).optional(),
});

// ── InterviewScheduler — schedule interview ────────────────────────────────
export const scheduleInterviewSchema = z.object({
    candidateId: z.string().min(1, 'Candidate is required'),
    interviewerIds: z.array(z.string().min(1)).min(1, 'At least one interviewer is required'),
    duration: z
        .number()
        .int()
        .min(15, 'Minimum 15 minutes')
        .max(480, 'Maximum 8 hours'),
    preferredDate: z.string().optional(),
    stage: z.string().optional(),
});

// ── AIChatbot — send message ───────────────────────────────────────────────
export const chatMessageSchema = z.object({
    message: z
        .string()
        .min(1, 'Message cannot be empty')
        .max(2000, 'Message too long (max 2000 characters)')
        .trim(),
});

// ── FeatureFlagAdmin — create/update flag ──────────────────────────────────
export const featureFlagSchema = z.object({
    name: z.string().min(2, 'Name must be at least 2 characters').max(200),
    key: z
        .string()
        .min(2, 'Key must be at least 2 characters')
        .max(100)
        .regex(/^[a-z][a-z0-9_]*$/, 'Key must be lowercase with underscores only (e.g. my_flag)'),
    description: z.string().max(500).optional(),
    rolloutPercentage: z.number().min(0).max(100),
    environment: z.string().min(1, 'Environment is required'),
    enabled: z.boolean(),
});

// ── PolicyManager — create/update policy ───────────────────────────────────
export const policySchema = z.object({
    title: z.string().min(5, 'Title must be at least 5 characters').max(300).trim(),
    type: z.enum(
        ['terms_of_service', 'privacy_policy', 'cookie_policy', 'dpa', 'acceptable_use'],
        { message: 'Select a valid policy type' },
    ),
    content: z
        .string()
        .min(100, 'Policy content must be at least 100 characters')
        .max(500000),
    effectiveDate: z.string().optional(),
});

// ── CompensationBenchmark — search ─────────────────────────────────────────
export const compensationSearchSchema = z.object({
    role: z
        .string()
        .min(2, 'Role title must be at least 2 characters')
        .max(200)
        .trim(),
    location: z.string().max(200).optional(),
    experienceLevel: z
        .enum(['junior', 'mid', 'senior', 'lead', 'executive'])
        .optional(),
});

// ── TalentSearch — search query ────────────────────────────────────────────
export const talentSearchSchema = z.object({
    query: z.string().max(500).trim().optional(),
    filters: z.object({
        remote: z.boolean().optional(),
        fullTime: z.boolean().optional(),
        senior: z.boolean().optional(),
        designSkills: z.boolean().optional(),
        engineeringSkills: z.boolean().optional(),
    }).optional(),
});
