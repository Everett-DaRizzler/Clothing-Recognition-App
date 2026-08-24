from .schema import ATTRIBUTES
def score(predictions, ground_truths):
    fields={a:[] for a in ATTRIBUTES}; parse=[]; failures=[]; times=[]
    for gt in ground_truths:
        gt_data=gt if isinstance(gt,dict) else gt.model_dump(); pred=predictions.get(gt_data["imageId"])
        if not pred: failures.append(gt_data["imageId"]); continue
        p=pred if isinstance(pred,dict) else pred.model_dump(); parse.append(bool(p.get("parseSuccess",True))); times.append(p.get("inferenceTimeMs",0))
        for a in ATTRIBUTES: fields[a].append(gt_data.get(a) is not None and gt_data.get(a)==p.get(a))
    accuracy={a: round(sum(v)/len(v),4) if v else None for a,v in fields.items()}; vals=[v for v in accuracy.values() if v is not None]
    return {"attributes":accuracy,"overallAttributeAccuracy":round(sum(vals)/len(vals),4) if vals else None,"jsonParseSuccessRate":round(sum(parse)/len(parse),4) if parse else 0,"inferenceFailureRate":round(len(failures)/len(ground_truths),4) if ground_truths else 0,"averageInferenceTimeMs":round(sum(times)/len(times)) if times else None,"failures":failures}
