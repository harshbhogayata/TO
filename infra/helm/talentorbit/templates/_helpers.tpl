{{/*
TalentOrbit Helm Chart — Template Helpers

Standard Kubernetes labelling conventions following:
  - app.kubernetes.io/name
  - app.kubernetes.io/instance
  - app.kubernetes.io/version
  - app.kubernetes.io/component
  - app.kubernetes.io/part-of
  - app.kubernetes.io/managed-by
*/}}

{{/*
Chart name (truncated to 63 chars, trimmed of trailing hyphens).
*/}}
{{- define "talentorbit.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name — <release>-<chart> (max 63 chars).
If release name already contains chart name, don't double up.
*/}}
{{- define "talentorbit.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label value: <chart>-<version>
*/}}
{{- define "talentorbit.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "talentorbit.labels" -}}
helm.sh/chart: {{ include "talentorbit.chart" . }}
app.kubernetes.io/part-of: talentorbit
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion | quote }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{ include "talentorbit.selectorLabels" . }}
{{- end }}

{{/*
Selector labels (subset of common labels used in matchLabels).
*/}}
{{- define "talentorbit.selectorLabels" -}}
app.kubernetes.io/name: {{ include "talentorbit.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component-specific selector labels.
Usage: {{ include "talentorbit.componentLabels" (dict "root" . "component" "api") }}
*/}}
{{- define "talentorbit.componentLabels" -}}
{{ include "talentorbit.selectorLabels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Service account name — uses custom name or generates one.
*/}}
{{- define "talentorbit.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "talentorbit.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Container image reference — handles global registry prefix.
*/}}
{{- define "talentorbit.image" -}}
{{- $registry := .Values.global.imageRegistry -}}
{{- $repository := .Values.image.repository -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
PgBouncer image reference.
*/}}
{{- define "talentorbit.pgbouncerImage" -}}
{{- $registry := .Values.global.imageRegistry -}}
{{- $repository := .Values.pgbouncer.image.repository -}}
{{- $tag := .Values.pgbouncer.image.tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
Namespace — prefer explicit value, fall back to Release.Namespace.
*/}}
{{- define "talentorbit.namespace" -}}
{{- .Values.namespace.name | default .Release.Namespace }}
{{- end }}

{{/*
Standard environment variables shared across all backend pods.
Mounts from ConfigMap and Secret references.
*/}}
{{- define "talentorbit.envVars" -}}
- name: DJANGO_SETTINGS_MODULE
  value: "talentorbit.settings"
- name: DEBUG
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: DEBUG
- name: ALLOWED_HOSTS
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: ALLOWED_HOSTS
- name: FRONTEND_URL
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: FRONTEND_URL
- name: CORS_ALLOWED_ORIGINS
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: CORS_ALLOWED_ORIGINS
- name: DEFAULT_FROM_EMAIL
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: DEFAULT_FROM_EMAIL
- name: R2_BUCKET_NAME
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: R2_BUCKET_NAME
- name: R2_ENDPOINT_URL
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: R2_ENDPOINT_URL
- name: R2_CUSTOM_DOMAIN
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: R2_CUSTOM_DOMAIN
- name: SENTRY_DSN
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: SENTRY_DSN
- name: SENTRY_TRACES_SAMPLE_RATE
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: SENTRY_TRACES_SAMPLE_RATE
- name: POSTHOG_HOST
  valueFrom:
    configMapKeyRef:
      name: {{ include "talentorbit.fullname" . }}-config
      key: POSTHOG_HOST
{{- /* Secrets */ -}}
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: SECRET_KEY
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: DATABASE_URL
- name: UPSTASH_REDIS_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: REDIS_URL
- name: CHANNELS_REDIS_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: CHANNELS_REDIS_URL
- name: CELERY_BROKER_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: CELERY_BROKER_URL
- name: STRIPE_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: STRIPE_SECRET_KEY
- name: STRIPE_WEBHOOK_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: STRIPE_WEBHOOK_SECRET
- name: R2_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: R2_ACCESS_KEY_ID
- name: R2_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: R2_SECRET_ACCESS_KEY
- name: RESEND_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: RESEND_API_KEY
- name: POSTHOG_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "talentorbit.fullname" . }}-secret
      key: POSTHOG_API_KEY
{{- /* PgBouncer-aware DATABASE_URL override when PgBouncer is enabled */ -}}
{{- if .Values.pgbouncer.enabled }}
- name: DATABASE_URL
  value: "postgres://{{ .Values.pgbouncer.auth.username }}:$(DATABASE_PASSWORD)@{{ include "talentorbit.fullname" . }}-pgbouncer:{{ .Values.pgbouncer.service.port }}/{{ (index .Values.pgbouncer.databases "talentorbit").dbname }}"
{{- end }}
{{- end }}
