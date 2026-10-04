"""Regularized SMPL-X expression fitting to observed facial features.

The correspondence below is a manual selection of matching eyebrows, nose,
eyelids and lips in the standard 68-point layout and MediaPipe's 478-point mesh.
This is an approximate monocular fit, not a reconstruction of personal likeness.
"""
# Inner 51 landmarks (68-point indices 17..67), without the view-dependent contour.
MP_FEATURES=(70,63,105,66,107,336,296,334,293,300,
             168,6,197,1,98,97,2,326,327,
             33,160,158,133,153,144,362,385,387,263,373,380,
             61,40,37,0,267,270,291,321,314,17,84,91,78,82,13,312,308,317,14,87)


def fit(model,params,details,K,iterations=18):
    import torch
    import numpy as np
    n=len(params['transl']);device=model.v_template.device
    inc=params.get('incam') or (params if params.get('cam_to_yup') else None)
    count=model.num_expression_coeffs
    params['expression']=[[0.]*count for _ in range(n)]
    for key in ('jaw_pose','leye_pose','reye_pose'):params[key]=[[0.]*3 for _ in range(n)]
    if not inc or not K or not details:return params
    ids=[i for i,d in enumerate(details) if d and d.get('face') and len(d['face']['image'])>=478]
    if not ids:return params
    tensor=lambda v:torch.tensor(v,dtype=torch.float32,device=device)
    betas=np.asarray(params.get('betas') or [0.]*10,dtype=np.float32)
    if betas.ndim>1:betas=betas.mean(axis=0)
    betas=betas[:10];intrinsics=tensor(K)
    residuals=[];initial_residuals=[]
    def normalize(points):
        center=points[:,13:14]
        scale=torch.linalg.vector_norm(points[:,19]-points[:,28],dim=-1).clamp(min=4)
        return (points-center)/scale[:,None,None]
    for start in range(0,len(ids),8):
        frames=ids[start:start+8];batch=len(frames)
        target=tensor([[details[i]['face']['image'][j][:2] for j in MP_FEATURES] for i in frames])
        normalized_target=normalize(target)
        expression=torch.zeros(batch,count,device=device,requires_grad=True)
        jaw=tensor([[float(details[i]['face']['blendshapes'].get('jawOpen',0))*.5,0,0] for i in frames]).requires_grad_()
        head=torch.zeros(batch,3,device=device,requires_grad=True)
        bp=tensor([inc['body_pose'][i][:63] for i in frames])
        go=tensor([inc['global_orient'][i] for i in frames]);tr=tensor([inc['transl'][i] for i in frames])
        shape=tensor(np.broadcast_to(betas,(batch,10)).copy())
        eyes=torch.zeros(batch,3,device=device)
        left_hand=tensor([params.get('left_hand_pose',[[0.]*45]*n)[i] for i in frames])
        right_hand=tensor([params.get('right_hand_pose',[[0.]*45]*n)[i] for i in frames])
        optimizer=torch.optim.Adam([expression,jaw,head],lr=.045)
        for step in range(iterations):
            optimizer.zero_grad()
            adjusted=torch.cat((bp[:,:42],bp[:,42:45]+head,bp[:,45:]),dim=1)
            prediction=model(betas=shape,global_orient=go,body_pose=adjusted,transl=tr,
                             expression=expression,jaw_pose=jaw,leye_pose=eyes,reye_pose=eyes,
                             left_hand_pose=left_hand,right_hand_pose=right_hand,return_verts=False)
            landmarks=prediction.joints[:,-51:]
            projected=landmarks@intrinsics.T
            pixels=projected[:,:,:2]/projected[:,:,2:].clamp(min=.1)
            error=(normalize(pixels)-normalized_target).square().mean()
            if step==0:initial_residuals.append(float(error.detach().cpu()))
            loss=error+.001*expression.square().mean()+.08*head.square().mean()+.02*jaw[:,1:].square().mean()
            loss.backward();optimizer.step()
            with torch.no_grad():
                expression.clamp_(-3,3);head.clamp_(-.4,.4);jaw[:,0].clamp_(0,.7);jaw[:,1:].clamp_(-.15,.15)
        for j,i in enumerate(frames):
            params['expression'][i]=expression[j].detach().cpu().tolist()
            params['jaw_pose'][i]=jaw[j].detach().cpu().tolist()
            delta=head[j].detach().cpu().tolist()
            for axis in range(3):
                params['body_pose'][i][42+axis]+=delta[axis]
                if 'incam' in params:params['incam']['body_pose'][i][42+axis]+=delta[axis]
            bs=details[i]['face']['blendshapes']
            for side in ('left','right'):
                suffix='Left' if side=='left' else 'Right';sign=1 if side=='left' else -1
                params['leye_pose' if side=='left' else 'reye_pose'][i]=[
                    .2*(bs.get('eyeLookDown'+suffix,0)-bs.get('eyeLookUp'+suffix,0)),
                    sign*.25*(bs.get('eyeLookIn'+suffix,0)-bs.get('eyeLookOut'+suffix,0)),0.]
        residuals.append(float(error.detach().cpu()))
        print(__import__('json').dumps({'stage':'face-fit','progress':min(1,(start+batch)/len(ids)),
            'message':'SMPL-X: подгоняю мимику…'},ensure_ascii=True),flush=True)
    if not all(__import__('math').isfinite(v) for v in residuals):raise RuntimeError('Non-finite face fit')
    params['expression_source']='MediaPipe feature fit; approximate monocular expression'
    params['face_fit_frames']=len(ids);params['face_fit_normalized_mse']=sum(residuals)/len(residuals)
    params['face_fit_initial_mse']=sum(initial_residuals)/len(initial_residuals)
    return params
