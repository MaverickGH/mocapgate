"""Finger articulation, ambiguous ownership and optional capture exports."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core import smpl, smpl_bvh, pipeline
from core.hand_bvh import add_fingers, palm_points, FINGERS
from core.detail_worker import owner
from core.skeleton import joint_names
from core.rotations import axis_angle_to_matrix, mat_vec


def hand():
    points = [[0.,0.,0.] for _ in range(21)]
    for finger, start in FINGERS:
        y = {'Thumb':.045,'Index':.03,'Middle':0,'Ring':-.02,'Pinky':-.04}[finger]
        for k in range(4): points[start+k]=[.055+k*.025,y,0.]
    return points


class DetailCapture(unittest.TestCase):
    def test_ambiguous_crossing_does_not_steal_another_persons_hand(self):
        hints=[(1,{'wrists':{'left':[100,100,40]}}),(2,{'wrists':{'right':[140,100,40]}})]
        self.assertEqual(owner([101,100],hints,'wrists'),(1,'left'))
        self.assertEqual(owner([139,100],hints,'wrists'),(2,'right'))
        self.assertIsNone(owner([120,100],hints,'wrists'))
        self.assertIsNone(owner([400,100],hints,'wrists'))

    def test_palm_coordinates_are_camera_rotation_and_translation_invariant(self):
        points=hand(); matrix=axis_angle_to_matrix([.6,-.4,1.2])
        moved=[[v+offset for v,offset in zip(mat_vec(matrix,p),[4,-3,2])] for p in points]
        for side in ('left','right'):
            for a,b in zip(palm_points(points,side),palm_points(moved,side)):
                for x,y in zip(a,b): self.assertAlmostEqual(x,y,places=8)

    def test_fingers_animate_and_long_gaps_return_to_neutral(self):
        params={'global_orient':[[0]*3]*12,'body_pose':[[0]*63]*12,'transl':[[0]*3]*12}
        root,frames=smpl_bvh.convert(params)
        curled=hand();curled[10]=[.06,0,-.035];curled[11]=[.04,0,-.06];curled[12]=[.02,0,-.06]
        details=[{'hands':{'left':{'world':hand()}}},{'hands':{'left':{'world':curled}}}]+[None]*10
        root,frames=add_fingers(root,frames,details,30)
        self.assertEqual(len(joint_names(root)),52)
        self.assertNotEqual(frames[0]['LeftHandMiddle1']['rot'],frames[1]['LeftHandMiddle1']['rot'])
        self.assertEqual(frames[1]['LeftHandMiddle1']['rot'],frames[2]['LeftHandMiddle1']['rot'])
        self.assertTrue(all(abs(v)%360<1e-6 for v in frames[-1]['LeftHandMiddle1']['rot']))
        self.assertEqual(frames[-1]['RightHandIndex1']['rot'],(0.,0.,0.))

    def test_face_export_keeps_blendshapes_and_missing_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            take=Path(tmp);params={'global_orient':[[0]*3]*2,'body_pose':[[0]*63]*2,'transl':[[0,1,0]]*2}
            detail={'hands':{'left':{'world':hand(),'image':[[10,20,0]]*21}},
                    'face':{'image':[[10,20,0]]*478,'blendshapes':{'jawOpen':.7}}}
            out={'id':3,'fps':30,'params':params,'details':[detail,None],'detail_size':[640,480]}
            meta={'name':'capture'}
            result=pipeline.write_person(take,meta,out,{'capture_hands':True,'foot_lock':False},None,False)
            self.assertEqual(result['capture_counts'],{'left':1,'right':0,'face':1})
            data=json.loads((take/result['capture_file']).read_text())
            self.assertEqual(data['id'],3);self.assertIsNone(data['frames'][1])
            self.assertEqual(data['frames'][0]['face']['blendshapes']['jawOpen'],.7)
            self.assertIn('LeftHandThumb3',(take/result['bvh']).read_text())

    def test_details_off_preserves_body_only_skeleton(self):
        params={'global_orient':[[0]*3],'body_pose':[[0]*63],'transl':[[0]*3]}
        root,_=smpl_bvh.convert(params)
        self.assertEqual(len(joint_names(root)),22)

    def test_camera_space_result_has_overlay_for_hand_and_face_preview(self):
        params={'global_orient':[[0]*3],'body_pose':[[0]*63],'transl':[[0,0,4]],
                'cam_to_yup':True,'K':[[500,0,320],[0,500,240],[0,0,1]]}
        overlay=pipeline.overlay_for(Path('.'),{}, {'params':params,'fps':30},smpl.DEFAULT_REST)
        self.assertEqual(overlay['width'],640)
        self.assertEqual(len(overlay['skeleton'][0]),22)


if __name__=='__main__': unittest.main()
