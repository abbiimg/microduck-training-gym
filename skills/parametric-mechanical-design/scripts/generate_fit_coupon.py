"""Two-engine fit fixture; dimensions are mm. Source + params remain authoritative."""
import argparse,re,hashlib,importlib.metadata,json,math,pathlib,sys


def generate(engine,params,out):
    required=['width_mm','depth_mm','plate_mm','hole_diameter_mm','pin_diameter_mm','pin_height_mm']
    for key in required:
        if not isinstance(params.get(key),(float,int)) or not math.isfinite(params[key]) or params[key]<=0:raise ValueError(key+' must be finite and positive')
    w,d,t,hd,pd,ph=[params[k] for k in required]
    if hd>=min(w,d) or pd>=hd or ph<=t:raise ValueError('Fixture requires a through-hole inside the plate and a smaller, taller pin')
    out=pathlib.Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    prefix=re.sub(r'[^A-Za-z0-9_]', '_', engine+'_'+out.name)
    expected={'plate_volume_mm3':(w*d-math.pi*(hd/2)**2)*t,'pin_volume_mm3':math.pi*(pd/2)**2*ph,'assembly_size_mm':[w,d,ph]}
    if engine=='cadquery':
        print('Loading CadQuery',flush=True)
        import cadquery as cq
        print('Building CadQuery fixture',flush=True)
        plate=cq.Workplane('XY').box(w,d,t,centered=(False,False,False)).faces('>Z').workplane(centerOption='CenterOfMass').hole(hd)
        pin=cq.Workplane('XY').circle(pd/2).extrude(ph)
        plate_name=prefix+'_plate';pin_name=prefix+'_pin'
        assembly=cq.Assembly(name='Parametric_Fit_Coupon_'+prefix).add(plate,name=plate_name).add(pin,name=pin_name)
        assembly.constrain(plate_name,'Fixed')
        assembly.constrain(plate_name+'@faces@<Z',pin_name+'@faces@<Z','Point')
        assembly.constrain(plate_name+'@faces@%CYLINDER',pin_name+'@faces@%CYLINDER','Axis',param=0)
        assembly.solve()
        print('CadQuery constraints solved',flush=True)
        shape=assembly.toCompound();box=shape.BoundingBox()
        measured={'plate_volume_mm3':plate.val().Volume(),'pin_volume_mm3':pin.val().Volume(),'assembly_size_mm':[box.xlen,box.ylen,box.zlen]}
        assert plate.val().isValid() and pin.val().isValid()
        located_pin=pin.val().located(assembly.objects[pin_name].loc)
        center=located_pin.Center();assert abs(center.x-w/2)<.001 and abs(center.y-d/2)<.001 and abs(center.z-ph/2)<.001,(center.x,center.y,center.z)
        assert abs(plate.val().intersect(located_pin).Volume())<1e-6
        assembly.export(str(out/'assembly.step'))
        shape.exportStl(str(out/'assembly.stl'),tolerance=.01,angularTolerance=.1)
        imported=cq.importers.importStep(str(out/'assembly.step')).val()
        solids=len(imported.Solids());volume=imported.Volume()
        method='CadQuery assembly Point and Axis constraints solved with plate fixed'
    else:
        print('Loading build123d',flush=True)
        import build123d as b
        print('Building build123d fixture',flush=True)
        plate=b.Box(w,d,t,align=(b.Align.MIN,b.Align.MIN,b.Align.MIN))-b.Pos(w/2,d/2,0)*b.Cylinder(hd/2,t,align=(b.Align.CENTER,b.Align.CENTER,b.Align.MIN))
        pin=b.Cylinder(pd/2,ph,align=(b.Align.CENTER,b.Align.CENTER,b.Align.MIN))
        plate.label=prefix+'_plate';pin.label=prefix+'_pin'
        b.RigidJoint('mount',to_part=plate,joint_location=b.Location((w/2,d/2,0)))
        b.RigidJoint('origin',to_part=pin,joint_location=b.Location((0,0,0)))
        plate.joints['mount'].connect_to(pin.joints['origin'])
        shape=b.Compound(children=[plate,pin],label='Parametric_Fit_Coupon');box=shape.bounding_box()
        measured={'plate_volume_mm3':plate.volume,'pin_volume_mm3':pin.volume,'assembly_size_mm':[box.size.X,box.size.Y,box.size.Z]}
        assert plate.is_valid and pin.is_valid
        pinbox=pin.bounding_box();assert abs((pinbox.min.X+pinbox.max.X)/2-w/2)<.001 and abs((pinbox.min.Y+pinbox.max.Y)/2-d/2)<.001
        overlap=plate&pin;assert overlap is None or abs(overlap.volume)<1e-6
        b.export_step(shape,str(out/'assembly.step'))
        b.export_stl(shape,str(out/'assembly.stl'),tolerance=.01,angular_tolerance=.1)
        imported=b.import_step(str(out/'assembly.step'));solids=len(imported.solids());volume=imported.volume
        method='build123d paired RigidJoint placement; no persistent mechanism solve claimed'
    for key in ['plate_volume_mm3','pin_volume_mm3']:
        assert abs(measured[key]-expected[key])<.001,(key,measured,expected)
    assert max(abs(a-b) for a,b in zip(measured['assembly_size_mm'],expected['assembly_size_mm']))<.001
    assert solids==2,solids
    assert abs(volume-expected['plate_volume_mm3']-expected['pin_volume_mm3'])<.01
    (out/'parameters.json').write_text(json.dumps(params,indent=2))
    manifest={'status':'PASS','engine':engine,'version':importlib.metadata.version(engine),'python':sys.executable,'units':'mm','axes':'XYZ preserved; Z up; plate bottom z=0','method':method,'parameters':params,'expected':expected,'measured':measured,'step_roundtrip':{'solid_count':solids,'volume_mm3':volume},'source_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'files':{p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in [out/'assembly.step',out/'assembly.stl',out/'parameters.json']}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=['cadquery','build123d'],required=True);p.add_argument('--params',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();generate(a.engine,json.loads(pathlib.Path(a.params).read_text()),a.output_dir)


