// Types based on schemas/investigation-report.schema.json

export const investigationReportSchema = {
  schema_version: 'string',
  investigation_id: 'string',
  observation_id: 'string',
  input_type: 'string',
  input_value: 'string',
  status: 'string',
  created_at: 'string',
  observation_data: 'object',
  module_results: 'object',
  overall_assessment: 'object',
  related_observations: 'array',
  graph_intelligence: 'object',
  evidence_references: 'array',
  graph_paths: 'array',
  warnings: 'array',
  algorithm_versions: 'object',
  execution_metadata: 'object',
};
