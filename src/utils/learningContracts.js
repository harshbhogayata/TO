const toNumber = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const asArray = (value) => (Array.isArray(value) ? value : []);
const asObject = (value) => (value && typeof value === 'object' ? value : {});

const buildDurationLabel = (minutes) => {
    const parsed = toNumber(minutes);
    return parsed && parsed > 0 ? `${parsed} min` : '';
};

const assessmentDifficultyMap = {
    1: 'easy',
    2: 'easy',
    3: 'medium',
    4: 'hard',
    5: 'expert',
};

const normaliseDifficulty = (value) => {
    const raw = String(value ?? '').trim().toLowerCase();
    if (raw && ['easy', 'medium', 'hard', 'expert'].includes(raw)) {
        return raw;
    }

    const numeric = toNumber(value);
    if (numeric !== null && assessmentDifficultyMap[numeric]) {
        return assessmentDifficultyMap[numeric];
    }

    return 'medium';
};

const normaliseSkillList = (value) =>
    asArray(value)
        .map((skill) => {
            if (typeof skill === 'string') {
                return skill;
            }

            if (skill?.name) {
                return skill.name;
            }

            return '';
        })
        .filter(Boolean);

const normaliseQuestionOptions = (options = []) =>
    asArray(options).map((option) => ({
        ...option,
        id: option?.id ?? option?.value,
        value: option?.value ?? option?.id,
        text: option?.text ?? option?.label ?? String(option?.value ?? option?.id ?? ''),
        label: option?.label ?? option?.text ?? String(option?.value ?? option?.id ?? ''),
    }));

const normaliseLessonProgress = (progress = null) => {
    if (!progress) {
        return null;
    }

    return {
        ...progress,
        progress_pct: toNumber(
            progress.progress_pct
            ?? progress.progress_percentage
            ?? progress.progress
            ?? progress.best_score
            ?? 0,
        ) ?? 0,
        is_completed: Boolean(progress.is_completed),
        time_spent_seconds: toNumber(progress.time_spent_seconds) ?? 0,
        video_position_seconds: toNumber(progress.video_position_seconds) ?? 0,
    };
};

const normaliseLesson = (lesson = {}) => {
    const progress = normaliseLessonProgress(lesson.progress);

    return {
        ...lesson,
        slug: lesson.slug ?? '',
        title: lesson.title ?? 'Untitled Lesson',
        text: lesson.text ?? lesson.question_text ?? lesson.title ?? '',
        question_text: lesson.question_text ?? lesson.text ?? lesson.title ?? '',
        estimated_duration_minutes: toNumber(lesson.estimated_duration_minutes) ?? 0,
        video_duration_seconds: toNumber(lesson.video_duration_seconds) ?? 0,
        progress,
        is_completed: Boolean(lesson.is_completed ?? progress?.is_completed),
    };
};

const normaliseModule = (module = {}) => ({
    ...module,
    title: module.title ?? 'Untitled Module',
    lessons: asArray(module.lessons).map(normaliseLesson),
});

const normaliseInstructorName = (course = {}) => {
    if (course.instructor_name) {
        return course.instructor_name;
    }

    if (Array.isArray(course.instructors) && course.instructors.length > 0) {
        const names = course.instructors
            .map((instructor) => instructor?.name ?? instructor?.user_name ?? instructor?.user?.full_name)
            .filter(Boolean);

        if (names.length > 0) {
            return names.join(', ');
        }
    }

    return course.instructor?.name ?? course.instructor?.full_name ?? 'TBA';
};

export const normaliseEnrollment = (enrollment = {}) => {
    const progressPct = toNumber(
        enrollment.progress_pct
        ?? enrollment.progress_percentage
        ?? enrollment.progress
        ?? 0,
    ) ?? 0;

    return {
        ...enrollment,
        course_slug: enrollment.course_slug ?? enrollment.course?.slug ?? '',
        course_title: enrollment.course_title ?? enrollment.course?.title ?? 'Untitled Course',
        progress_pct: progressPct,
        progress_percentage: progressPct,
        last_lesson_id: enrollment.last_lesson_id ?? enrollment.last_lesson?.id ?? enrollment.last_lesson ?? null,
        last_lesson_slug: enrollment.last_lesson_slug ?? enrollment.last_lesson?.slug ?? '',
        has_certificate: Boolean(enrollment.has_certificate),
    };
};

export const normaliseCourseListItem = (course = {}) => ({
    ...course,
    slug: course.slug ?? '',
    thumbnail: course.thumbnail ?? course.thumbnail_url ?? '',
    thumbnail_url: course.thumbnail_url ?? course.thumbnail ?? '',
    instructor_name: normaliseInstructorName(course),
    estimated_duration_minutes: toNumber(course.estimated_duration_minutes) ?? 0,
    estimated_duration: course.estimated_duration ?? buildDurationLabel(course.estimated_duration_minutes),
});

export const normaliseCourseDetail = (course = {}) => {
    const normalised = normaliseCourseListItem(course);
    const enrollment = course.enrollment ? normaliseEnrollment(course.enrollment) : null;

    return {
        ...normalised,
        modules: asArray(course.modules ?? course.curriculum).map(normaliseModule),
        enrollment,
        is_enrolled: Boolean(course.is_enrolled ?? enrollment),
        prerequisites: asArray(course.prerequisites),
        description: course.description ?? course.short_description ?? '',
    };
};

export const normaliseCourseProgress = (data = {}, course = null) => {
    const normalisedCourse = course ? normaliseCourseDetail(course) : null;
    const enrollment = normaliseEnrollment(data.enrollment ?? {});
    const moduleStats = asArray(data.modules);
    const moduleStatsById = new Map(moduleStats.map((module) => [module.module_id ?? module.id, module]));
    const lessonStatuses = asObject(data.lesson_statuses);

    const modules = asArray(normalisedCourse?.modules).map((module) => {
        const moduleStatus = moduleStatsById.get(module.id) ?? {};

        return {
            ...module,
            completed_lessons: toNumber(moduleStatus.completed_lessons) ?? 0,
            total_lessons: toNumber(moduleStatus.total_lessons) ?? module.lessons.length,
            percentage: toNumber(moduleStatus.percentage) ?? 0,
            lessons: module.lessons.map((lesson) => {
                const status = asObject(
                    lessonStatuses[String(lesson.id)]
                    ?? lessonStatuses[String(lesson.slug)]
                    ?? {},
                );
                const mergedProgress = normaliseLessonProgress(status.progress ?? status ?? lesson.progress);

                return {
                    ...lesson,
                    progress: mergedProgress,
                    is_completed: Boolean(status.completed ?? mergedProgress?.is_completed ?? lesson.is_completed),
                };
            }),
        };
    });

    return {
        ...data,
        enrollment,
        modules,
        overall_progress: toNumber(data.overall_progress ?? enrollment.progress_percentage) ?? 0,
        completed_lessons: toNumber(data.completed_lessons ?? enrollment.lessons_completed) ?? 0,
        total_lessons: toNumber(data.total_lessons) ?? modules.reduce((total, module) => total + module.lessons.length, 0),
        next_lesson: data.next_lesson ?? null,
        lesson_statuses: lessonStatuses,
    };
};

export const getCourseSlug = (value) =>
    value?.course_slug
    ?? value?.slug
    ?? value?.course?.slug
    ?? (typeof value === 'string' ? value : '');

export const getLessonSlug = (value) =>
    value?.last_lesson_slug
    ?? value?.lesson_slug
    ?? value?.slug
    ?? value?.last_lesson?.slug
    ?? '';

export const getCourseRoute = (course) => {
    const courseSlug = getCourseSlug(course);
    return courseSlug ? `/courses/${courseSlug}` : '/courses';
};

export const getCourseProgressRoute = (course) => {
    const courseSlug = getCourseSlug(course);
    return courseSlug ? `/courses/${courseSlug}/progress` : '/my-learning';
};

export const getLessonRoute = (course, lesson) => {
    const courseSlug = getCourseSlug(course);
    const lessonSlug = getLessonSlug(lesson) || lesson?.slug || '';

    if (!courseSlug || !lessonSlug) {
        return getCourseProgressRoute(course);
    }

    return `/courses/${courseSlug}/lessons/${lessonSlug}`;
};

export const getEnrollmentRoute = (enrollment, { preferContinue = true } = {}) => {
    if (preferContinue) {
        const lessonRoute = getLessonRoute(enrollment, enrollment);
        if (lessonRoute !== getCourseProgressRoute(enrollment)) {
            return lessonRoute;
        }
    }

    return getCourseProgressRoute(enrollment);
};

const normaliseAttemptAnswerValue = (answer) => {
    if (answer == null) {
        return '';
    }

    const record = asObject(answer);

    if (Array.isArray(record.selected_option_ids) && record.selected_option_ids.length > 0) {
        return record.selected_option_ids.length === 1
            ? record.selected_option_ids[0]
            : [...record.selected_option_ids];
    }

    if (typeof record.boolean_answer === 'boolean') {
        return record.boolean_answer;
    }

    if (Array.isArray(record.ordering_answer) && record.ordering_answer.length > 0) {
        return [...record.ordering_answer];
    }

    if (record.code_answer) {
        return record.code_answer;
    }

    if (record.text_answer) {
        return record.text_answer;
    }

    return '';
};

const normaliseAnswerMap = (answers = {}) => {
    if (Array.isArray(answers)) {
        return Object.fromEntries(
            answers.map((answer) => [
                String(answer.question ?? answer.question_id ?? ''),
                normaliseAttemptAnswerValue(answer),
            ]).filter(([questionId]) => questionId),
        );
    }

    return Object.fromEntries(
        Object.entries(asObject(answers)).map(([questionId, answer]) => [
            String(questionId),
            normaliseAttemptAnswerValue(answer),
        ]),
    );
};

export const normaliseAssessmentListItem = (assessment = {}) => ({
    ...assessment,
    description: assessment.description ?? assessment.short_description ?? '',
    difficulty: normaliseDifficulty(assessment.difficulty ?? assessment.difficulty_level),
    time_limit_minutes: toNumber(assessment.time_limit_minutes ?? assessment.total_time_minutes ?? assessment.duration) ?? 0,
    question_count: toNumber(assessment.question_count ?? assessment.total_questions) ?? 0,
    passing_score: toNumber(assessment.passing_score ?? assessment.passing_score_percent) ?? 0,
    skills: normaliseSkillList(assessment.skills ?? assessment.tags ?? assessment.skills_tested_data),
    owner_company_name: assessment.owner_company_name ?? assessment.company_name ?? '',
    is_proctored: Boolean(assessment.is_proctored ?? assessment.proctoring_enabled),
});

export const normaliseAssessmentDetail = (assessment = {}) => {
    const normalised = normaliseAssessmentListItem(assessment);

    return {
        ...normalised,
        creator_name: assessment.creator_name ?? assessment.owner_company_name ?? 'TalentOrbit',
        my_attempts: asArray(assessment.my_attempts ?? assessment.user_attempts).map((attempt) => ({
            ...attempt,
            score: toNumber(attempt.score ?? attempt.score_percent) ?? null,
            completed_at: attempt.completed_at ?? attempt.submitted_at ?? attempt.created_at ?? null,
        })),
        remaining_attempts: assessment.remaining_attempts,
        can_start: assessment.can_start !== false,
        instructions: assessment.instructions ?? '',
    };
};

export const normaliseAssessmentAttempt = (attempt = {}) => {
    const questions = asArray(attempt.questions).map((question) => ({
        ...question,
        text: question.text ?? question.question_text ?? question.title ?? '',
        question_text: question.question_text ?? question.text ?? question.title ?? '',
        options: normaliseQuestionOptions(question.options ?? question.choices),
        section_index: toNumber(question.section_index) ?? 0,
    }));
    const flaggedQuestionIds = Array.isArray(attempt.flagged_question_ids)
        ? attempt.flagged_question_ids
        : Array.isArray(attempt.flagged)
            ? attempt.flagged
            : Object.entries(asObject(attempt.flagged))
                .filter(([, isFlagged]) => Boolean(isFlagged))
                .map(([questionId]) => questionId);

    return {
        ...attempt,
        questions,
        answers: normaliseAnswerMap(attempt.answers),
        flagged: flaggedQuestionIds.map((questionId) => String(questionId)),
        timeRemaining: toNumber(
            attempt.timeRemaining
            ?? attempt.time_remaining
            ?? attempt.time_remaining_seconds
            ?? 0,
        ) ?? 0,
        status: attempt.status ?? 'in_progress',
    };
};

export const buildAssessmentAnswerPayload = (question, value, options = {}) => {
    const payload = {
        question_id: question.id,
        section_index: toNumber(question.section_index) ?? 0,
        time_spent_seconds: toNumber(options.timeSpentSeconds) ?? 0,
        is_bookmarked: Boolean(options.isBookmarked),
    };

    switch (question.question_type) {
        case 'multi_select':
            payload.selected_option_ids = asArray(value)
                .map((optionId) => toNumber(optionId))
                .filter((optionId) => optionId !== null);
            break;
        case 'true_false':
            payload.boolean_answer = typeof value === 'string'
                ? value.toLowerCase() === 'true'
                : Boolean(value);
            break;
        case 'short_answer':
        case 'essay':
            payload.text_answer = String(value ?? '');
            break;
        case 'code':
            payload.code_answer = String(value ?? '');
            payload.code_language = question.code_execution_language ?? question.code_language ?? '';
            break;
        case 'ordering':
            payload.ordering_answer = asArray(value).map(String);
            break;
        case 'mcq':
        default: {
            const selectedOption = toNumber(value);
            payload.selected_option_ids = selectedOption === null ? [] : [selectedOption];
            break;
        }
    }

    return payload;
};

const normaliseSkillBreakdown = (result = {}) => {
    if (Array.isArray(result.skill_breakdown)) {
        return result.skill_breakdown.map((item) => ({
            ...item,
            name: item.name ?? item.skill ?? '',
            score: toNumber(item.score ?? item.percentage) ?? 0,
        }));
    }

    if (result.skill_scores && typeof result.skill_scores === 'object') {
        return Object.entries(result.skill_scores).map(([skill, score]) => ({
            name: skill,
            score: toNumber(score) ?? 0,
        }));
    }

    return [];
};

export const normaliseAssessmentResult = (result = {}) => {
    const answeredCount = toNumber(result.questions_answered)
        ?? (
            (toNumber(result.questions_correct) ?? 0)
            + (toNumber(result.questions_incorrect) ?? 0)
            + (toNumber(result.questions_partial) ?? 0)
        );
    const totalQuestions = toNumber(
        result.total_questions
        ?? result.question_count
        ?? (answeredCount + (toNumber(result.questions_skipped) ?? 0)),
    ) ?? 0;

    return {
        ...result,
        score: toNumber(result.score ?? result.percentage ?? result.percentage_score) ?? 0,
        percentage: toNumber(result.percentage ?? result.percentage_score ?? result.score) ?? 0,
        correct_count: toNumber(result.correct_count ?? result.questions_correct) ?? 0,
        total_questions: totalQuestions,
        question_count: totalQuestions,
        time_taken_seconds: toNumber(result.time_taken_seconds ?? result.total_time_seconds) ?? null,
        percentile: toNumber(result.percentile ?? result.percentile_rank) ?? null,
        skill_breakdown: normaliseSkillBreakdown(result),
        answers: asArray(result.answers),
        badge: result.badge ?? null,
        show_answers: Boolean(result.show_answers ?? asArray(result.answers).length > 0),
    };
};

export const normaliseAssessmentResultListItem = (result = {}) => {
    const normalised = normaliseAssessmentResult(result);

    return {
        ...normalised,
        attempt_id: result.attempt_id ?? result.attempt?.id ?? null,
        assessment_id: result.assessment_id ?? result.assessment?.id ?? result.assessment ?? null,
        completed_at: result.completed_at ?? result.graded_at ?? result.created_at ?? null,
    };
};

