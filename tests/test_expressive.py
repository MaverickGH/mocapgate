"""Full SMPL-X hierarchy and expressive-channel export checks without licensed assets."""
import math
import random
import unittest
from core import expressive, smpl
from core.bvh import write
from core.rotations import axis_angle_to_matrix, matmul, mat_vec
from test_smpl_bvh import parse_bvh, bvh_fk

PARENTS=list(smpl.PARENTS)+[15,15,15]
for wrist,first in ((20,25),(21,40)):
    for finger in range(5): PARENTS.extend([wrist,first+finger*3,first+finger*3+1])

class ExpressiveExport(unittest.TestCase):
    def test_all_55_joints_keep_exact_hierarchy_and_world_positions(self):
        rng=random.Random(18)
        rest=[[rng.uniform(-.5,.5) for _ in range(3)] for _ in range(55)]
        params={'transl':[[.3,1.1,-2]],'global_orient':[[.2,-.4,.5]],
                'body_pose':[[rng.uniform(-.8,.8) for _ in range(63)]]}
        for key,size in (('jaw_pose',3),('leye_pose',3),('reye_pose',3),('left_hand_pose',45),('right_hand_pose',45)):
            params[key]=[[rng.uniform(-.3,.3) for _ in range(size)]]
        rv=[params['global_orient'][0]]+[params['body_pose'][0][i:i+3] for i in range(0,63,3)]
        for key in ('jaw_pose','leye_pose','reye_pose','left_hand_pose','right_hand_pose'):
            rv.extend(params[key][0][i:i+3] for i in range(0,len(params[key][0]),3))
        positions=[];rotations=[]
        for i,parent in enumerate(PARENTS):
            rotation=axis_angle_to_matrix(rv[i])
            if parent<0:
                rotations.append(rotation);positions.append([rest[0][k]+params['transl'][0][k] for k in range(3)])
            else:
                rotations.append(matmul(rotations[parent],rotation))
                offset=mat_vec(rotations[parent],[rest[i][k]-rest[parent][k] for k in range(3)])
                positions.append([positions[parent][k]+offset[k] for k in range(3)])
        for camera in (False,True):
            params['cam_to_yup']=camera
            root,frames=expressive.to_bvh(params,rest,PARENTS,{})
            names,parents,offsets,channels,rows=parse_bvh(write(root,frames))
            self.assertEqual(set(names),set(expressive.NAMES));self.assertEqual(len(names),55)
            actual=bvh_fk(names,parents,offsets,channels,rows[0])
            for i,name in enumerate(names):
                model_index=expressive.NAMES.index(name);parent=PARENTS[model_index]
                self.assertEqual(names[parents[i]] if parents[i]>=0 else None,expressive.NAMES[parent] if parent>=0 else None)
                for axis in range(3):
                    expected=positions[model_index][axis]*100*(-1 if camera and axis>0 else 1)
                    self.assertAlmostEqual(actual[i][axis],expected,delta=.001)

    def test_face_correspondence_has_51_distinct_in_range_points(self):
        from core.face_fit import MP_FEATURES
        self.assertEqual(len(MP_FEATURES),51)
        self.assertEqual(len(set(MP_FEATURES)),51)
        self.assertTrue(all(0<=i<478 for i in MP_FEATURES))

