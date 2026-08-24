from PIL import Image
from wardrobe_backend.preprocessing import validate_and_prepare, InvalidImage
from wardrobe_backend.evaluation import score
def test_preprocess_writes_rgb(tmp_path):
    source=tmp_path/'a.png'; Image.new('RGBA',(400,200),'red').save(source); out=tmp_path/'w.jpg'; thumb=tmp_path/'t.jpg'; meta=validate_and_prepare(source,out,thumb,1000000); assert meta['width']==400 and out.exists() and thumb.exists()
def test_rejects_type(tmp_path):
    p=tmp_path/'a.txt'; p.write_text('x')
    try: validate_and_prepare(p,tmp_path/'w.jpg',tmp_path/'t.jpg',100)
    except InvalidImage: return
    assert False
def test_score_is_explainable():
    gt=[{'imageId':'1','category':'Top','type':'Polo','color':'Navy','pattern':'Solid'}]; pred={'1':{'category':'Top','type':'Polo','color':'Black','pattern':'Solid','parseSuccess':True,'inferenceTimeMs':100}}; result=score(pred,gt); assert result['attributes']['category']==1 and result['attributes']['color']==0
