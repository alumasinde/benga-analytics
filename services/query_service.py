from analyzer import build_insights
from database.repositories import RecordRepository

class QueryService:
    def __init__(self, database): self.records = RecordRepository(database)
    def execute(self, *, dataset, dataset_id, tenant_id, payload):
        schema=dataset["schema_metadata"]; dimensions=set(schema.get("dimensions", [])); metrics=set(schema.get("metrics", [])); dates=set(schema.get("dates", []))
        aggregation=str(payload.get("aggregation","sum")).lower(); metric=payload.get("metric"); group_by=payload.get("group_by"); filters=payload.get("filters",{}) or {}; search=str(payload.get("search","")).strip()
        if aggregation not in {"sum","avg","count"}: raise ValueError("Unsupported aggregation.")
        if group_by and group_by not in dimensions and group_by not in dates: raise ValueError("Invalid grouping field.")
        if aggregation != "count" and metric not in metrics: raise ValueError("Choose a valid numerical metric.")
        if not isinstance(filters, dict): raise ValueError("Filters must be an object.")
        valid_filters={field:values[:1000] for field,values in filters.items() if field in dimensions and isinstance(values,list) and values}
        rows, raw=self.records.query(dataset_id=dataset_id,tenant_id=tenant_id,aggregation=aggregation,metric=metric,group_by=group_by,filters=valid_filters,search=search,dimensions=list(dimensions))
        return {"rows":rows,"raw_records":raw,"insights":build_insights(rows,metric,aggregation,group_by),"query":{"metric":metric,"aggregation":aggregation,"group_by":group_by}}
