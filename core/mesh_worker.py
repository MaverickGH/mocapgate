"""SMPL-X surface generation in the configured torch/smplx environment.

Runs separately from Studio's stdlib Python. Licensed assets stay on this PC.
Outputs per-frame surface and exact model joints for the local Three.js viewer.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model'); ap.add_argument('motion'); ap.add_argument('output')
    args = ap.parse_args()
    import numpy as np
    import torch
    import smplx
    data = json.loads(Path(args.motion).read_text(encoding='utf-8'))
    params = data['params']; params['fps'] = data['fps']; n = len(params['transl'])
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = smplx.create(args.model,model_type='smplx',gender='neutral',ext='npz',
                         use_pca=False,flat_hand_mean=True,num_expression_coeffs=100).to(device).eval()
    for parameter in model.parameters():parameter.requires_grad_(False)
    def tensor(v): return torch.tensor(v,dtype=torch.float32,device=device)
    betas = np.asarray(params.get('betas') or [0.]*10,dtype=np.float32)
    if betas.ndim>1:betas=betas.mean(axis=0)
    betas=betas[:10]
    # Always use the same body shape across all frames and both mesh and skeleton.
    with torch.no_grad():
        neutral=model(betas=tensor(betas[None]),body_pose=torch.zeros(1,63,device=device))
    rest=neutral.joints[0,:55].cpu().numpy()
    from core.expressive import hands
    params=hands(params,data.get('details'),rest.tolist(),model.parents.tolist()) if data.get('capture_hands') else params
    if data.get('capture_face'):
        from core.face_fit import fit
        params=fit(model,params,data.get('details'),params.get('K'))
    vertices=[]; joints=[]
    for start in range(0,n,16):
        end=min(n,start+16); batch=end-start
        kwargs={key:tensor(params[key][start:end]) for key in ('global_orient','body_pose','transl')}
        kwargs['betas']=tensor(np.broadcast_to(betas,(batch,10)).copy())
        for key,size in (('left_hand_pose',45),('right_hand_pose',45),('jaw_pose',3),('leye_pose',3),('reye_pose',3),('expression',100)):
            kwargs[key]=tensor(params[key][start:end]) if key in params else torch.zeros(batch,size,device=device)
        with torch.no_grad():output=model(**kwargs,return_verts=True)
        v=output.vertices.cpu().numpy();j=output.joints[:,:55].cpu().numpy()
        if params.get('cam_to_yup'):
            v*=np.array([1,-1,-1],dtype=np.float32);j*=np.array([1,-1,-1],dtype=np.float32)
        vertices.append(v);joints.append(j)
        print(json.dumps({'stage':'mesh','progress':end/n,'message':'SMPL-X: поверхность тела…'},ensure_ascii=True),flush=True)
    vertices=np.concatenate(vertices);joints=np.concatenate(joints)
    if not np.isfinite(vertices).all() or not np.isfinite(joints).all():raise RuntimeError('Non-finite SMPL-X geometry')
    # Hip-relative geometry keeps sub-millimetre precision even on long world trajectories.
    relative=vertices-joints[:,0,None,:]
    scale=.0001
    if np.abs(relative).max()<3.27:
        packed=np.rint(relative/scale).astype('<i2');dtype='int16'
    else:
        packed=relative.astype('<f4');dtype='float32';scale=1.
    output=Path(args.output);binary=output.with_suffix('.bin')
    packed.tofile(binary)
    from core.expressive import NAMES, to_bvh
    from core.bvh import write, save
    from smplx.vertex_ids import vertex_ids
    end_offsets={}
    for side,short in (('Left','l'),('Right','r')):
        for finger in ('Thumb','Index','Middle','Ring','Pinky'):
            name=f'{side}Hand{finger}3';j=NAMES.index(name)
            tip=neutral.vertices[0,vertex_ids['smplx'][short+finger.lower()]].cpu().numpy()
            end_offsets[name]=(tip-rest[j]).tolist()
    root,frames=to_bvh(params,rest.tolist(),model.parents.tolist(),end_offsets)
    from core.mixamo import prepare
    head_top=neutral.vertices[0,neutral.vertices[0,:,1].argmax()].cpu().numpy()
    root,frames=prepare(root,frames,data.get('mixamo_namespace',False),(100*(head_top-rest[15])).tolist())
    save(output.with_suffix('.bvh'),write(root,frames,1/data['fps']))
    output.with_suffix('.params.json').write_text(json.dumps(params,separators=(',',':')),encoding='utf-8')
    result={'format':'mocapgate.mesh/1','model':'SMPL-X neutral','fps':data['fps'],'frames':n,
        'vertex_count':len(model.v_template),'faces':model.faces.tolist(), 'positions_file':binary.name,
        'dtype':dtype,'scale':scale,'origins':joints[:,0].tolist(),
        'joints':joints.tolist(),'joint_names':NAMES,'parents':model.parents.cpu().tolist(),'rest':rest.tolist(),
        'expression_source':params.get('expression_source','neutral')}
    output.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')


if __name__=='__main__':main()
