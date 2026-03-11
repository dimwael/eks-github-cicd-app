{{- define "eks-github-cicd-app.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s" $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "eks-github-cicd-app.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{ include "eks-github-cicd-app.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "eks-github-cicd-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "eks-github-cicd-app.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
