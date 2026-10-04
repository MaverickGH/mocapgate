import unittest
from core import smpl_bvh
from core.mixamo import prepare
from core.bvh import write
from core.skeleton import joint_names
from test_smpl_bvh import parse_bvh,bvh_fk

class MixamoExport(unittest.TestCase):
    def setUp(self):
        self.root,self.frames=smpl_bvh.convert({'global_orient':[[.4,-.3,.1]],'body_pose':[[.2]*63],'transl':[[1,2,3]]})

    def test_named_endpoints_do_not_change_original_joint_motion(self):
        old=parse_bvh(write(self.root,self.frames))
        root,frames=prepare(self.root,self.frames,True)
        names=joint_names(root)
        self.assertTrue(all(n.startswith('mixamorig:') for n in names))
        for tip in ('HeadTop_End','LeftToe_End','RightToe_End'):
            self.assertIn('mixamorig:'+tip,names)
            self.assertEqual(frames[0]['mixamorig:'+tip]['rot'],(0,0,0))
        new=parse_bvh(write(root,frames))
        before=bvh_fk(*old[:4],old[4][0]);after=bvh_fk(*new[:4],new[4][0])
        for name,point in zip(old[0],before):
            self.assertEqual(tuple(point),tuple(after[new[0].index('mixamorig:'+name)]))
        self.assertNotIn('mixamorig:Hips',self.frames[0])

    def test_finger_four_is_a_fixed_tip_and_conversion_is_idempotent(self):
        from core.hand_bvh import add_fingers
        root,frames=add_fingers(self.root,self.frames,[None],30)
        root,frames=prepare(root,frames)
        self.assertEqual(len(joint_names(root)),65)
        for side in ('Left','Right'):
            for finger in ('Thumb','Index','Middle','Ring','Pinky'):
                self.assertEqual(frames[0][side+'Hand'+finger+'4']['rot'],(0,0,0))
        second,second_frames=prepare(root,frames)
        self.assertEqual(write(root,frames),write(second,second_frames))
