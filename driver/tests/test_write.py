"""Exercise the real CRC transport and restricted FAT writer through the SPI model."""
import binascii
import ctypes as C
import hashlib
import importlib.util
import pathlib
import struct
import subprocess
import tempfile
import unittest
from support import library, ROOT
from fixture import TEXT,BIG

spec=importlib.util.spec_from_file_location('write_build',ROOT/'tests/kit_fixture.py')
builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)

class WFile(C.Structure):
    _fields_=[('first',C.c_uint32),('last',C.c_uint32),('size',C.c_uint32),('lba',C.c_uint32),
              ('offset',C.c_uint16),('directory',C.c_uint8)]

class WriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='otter-write-tests-'); cls.work=pathlib.Path(cls.tmp.name)
        so=library(cls.work,'write',['tests/reference/WSD.C','tests/reference/WFS.C','tests/reference/WTEST.C','tests/reference/HOSTIO.C',
                                    'FAT32.C','tests/emulation/slot_model.c'],['-std=c99','-I',str(ROOT/'tests/reference')])
        cls.lib=C.CDLL(str(so))
        cls.lib.wt_host_open.argtypes=[C.c_char_p,C.c_uint]
        cls.lib.sd_read.argtypes=[C.c_uint32,C.c_void_p]
        cls.lib.wt_write.argtypes=[C.c_uint32,C.c_void_p,C.c_int]
        cls.lib.wt_arm.argtypes=[C.c_uint32,C.c_uint32]
        cls.lib.wt_crc7.argtypes=[C.c_void_p,C.c_uint]; cls.lib.wt_crc7.restype=C.c_uint8
        cls.lib.wt_crc16.argtypes=[C.c_void_p,C.c_uint]; cls.lib.wt_crc16.restype=C.c_uint16
        cls.lib.wf_fat.argtypes=[C.c_uint32]; cls.lib.wf_fat.restype=C.c_uint32
        for n in ('wf_mkdir','wf_create'): getattr(cls.lib,n).argtypes=[C.c_uint32,C.c_char_p,C.POINTER(WFile)]
        cls.lib.wf_append.argtypes=[C.POINTER(WFile),C.c_void_p,C.c_uint]
        cls.lib.wf_overwrite.argtypes=[C.POINTER(WFile),C.c_uint32,C.c_void_p,C.c_uint]
        cls.lib.wf_truncate.argtypes=[C.POINTER(WFile),C.c_uint32]
        cls.lib.wf_delete.argtypes=[C.POINTER(WFile)]
        cls.lib.wf_rmdir.argtypes=[C.POINTER(WFile)]
        cls.lib.wt_host_config.argtypes=[C.c_uint,C.c_uint]
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        C.c_int.in_dll(self.lib,'wf_allow_hints').value=0
        C.c_int.in_dll(self.lib,'wt_no_crc').value=0
        C.c_int.in_dll(self.lib,'wt_crc_only').value=0
        C.c_int.in_dll(self.lib,'wt_normal_only').value=0
        C.c_int.in_dll(self.lib,'wt_probe_only').value=0
        self.image=self.work/'card.img'; self.layout=builder.prepare(self.image)
        self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),1),0)
        self.assertEqual(self.lib.sd_init(),0)
        self.buffer=C.create_string_buffer(512)
        self.scratch=self.layout['start']+8
    def tearDown(self): self.lib.wt_host_close()
    def error(self): return C.c_uint.in_dll(self.lib,'wt_error').value
    def poison(self): return C.c_uint.in_dll(self.lib,'wt_poison').value
    def arm(self): self.assertEqual(self.lib.wt_arm(self.scratch,self.scratch+1),0)
    def digest(self): return hashlib.sha256(self.image.read_bytes()).digest()
    def writes(self): return C.c_uint32.in_dll(self.lib,'wt_writes').value
    def begin(self):
        self.assertEqual(self.lib.wf_prepare(),0); self.assertEqual(self.lib.wf_begin(),0)
        d=WFile(); self.assertEqual(self.lib.wf_mkdir(2,b'WTEST',C.byref(d)),0); return d
    def check_partition(self):
        p=self.work/'partition.img'
        with self.image.open('rb') as f: f.seek(2048*512); p.write_bytes(f.read(self.layout['total']*512))
        result=subprocess.run(['fsck.fat','-n',str(p)],capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout.decode()+result.stderr.decode())
    def uint(self, name): return C.c_uint.in_dll(self.lib,name).value
    def suite_log(self):
        self.lib.wt_test_log.argtypes=[C.c_char_p]
        path=self.work/'suite.log'; self.lib.wt_test_log(str(path).encode())
        try: result=self.lib.wt_suite(1)
        finally: self.lib.wt_test_log(None)
        return result,path.read_text()
    def init_trace(self):
        n=self.uint('wt_init_count')
        commands=(C.c_uint*64).in_dll(self.lib,'wt_init_command')
        r1=(C.c_uint*64).in_dll(self.lib,'wt_init_r1')
        errors=(C.c_uint*64).in_dll(self.lib,'wt_init_error')
        return list(zip(commands[:n],r1[:n],errors[:n]))
    def test_ready_cmd55_still_requires_acmd41_and_card_validation(self):
        self.lib.wt_host_config(23,1); self.lib.wt_host_config(24,3)
        before=self.digest(); self.assertEqual(self.lib.sd_init(),0)
        trace=self.init_trace()
        self.assertEqual([r for cmd,r,e in trace if cmd==55],[0]*4)
        self.assertEqual([r for cmd,r,e in trace if cmd==41],[1,1,1,0])
        self.assertEqual([cmd for cmd,r,e in trace][-4:],[58,59,10,9])
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
        self.lib.wt_host_config(19,42)
        self.assertLess(self.lib.sd_init(),0); self.assertEqual(self.error(),101)
        self.assertEqual(self.init_trace()[-1],(41,255,101))
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_ready_cmd55_never_bypasses_rejected_acmd41_or_cid(self):
        self.lib.wt_host_config(23,1); before=self.digest()
        for command,error in ((55,106),(41,106),(10,103),(9,103)):
            self.lib.wt_host_config(18,command+1)
            self.assertLess(self.lib.sd_init(),0); self.assertEqual(self.error(),error)
            self.assertEqual(self.uint('wt_stage'),command)
            self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_startup_trace_retains_last_command_after_overflow(self):
        self.lib.wt_host_config(23,1); self.lib.wt_host_config(24,100)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.uint('wt_init_count'),64)
        self.assertGreater(C.c_uint32.in_dll(self.lib,'wt_init_total').value,64)
        self.assertEqual(self.init_trace()[0],(0,1,0))
        self.assertEqual(self.init_trace()[-1],(9,0,0))
        self.lib.wt_host_config(19,9)
        self.assertLess(self.lib.sd_init(),0)
        self.assertEqual(self.uint('wt_init_count'),2)
        self.assertEqual(self.init_trace()[-1],(8,255,101))
    def test_ready_cmd55_idle_acmd41_remains_bounded(self):
        self.lib.wt_host_config(23,1); self.lib.wt_host_config(24,1000000)
        before=self.digest(); self.assertLess(self.lib.sd_init(),0)
        self.assertEqual(self.error(),101); self.assertEqual(self.uint('wt_stage'),41)
        self.assertEqual(self.init_trace()[-1],(41,1,0))
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_ff_corruption_before_faults_stops_without_negative_probes(self):
        self.lib.wt_host_config(25,1); self.lib.wt_host_config(22,224)
        before=self.image.read_bytes(); result,log=self.suite_log()
        self.assertEqual(result,1); self.assertEqual(self.error(),105); self.assertTrue(self.poison())
        self.assertIn('phase=PRE-FAULT index=1 kind=FF',log)
        self.assertNotIn('PHASE: FAULT-PROBES',log)
        self.assertNotIn('PHASE: FILESYSTEM',log)
        self.assertIn('differing_bytes=508',log)
        self.assertIn('response=E5 CMD13_R1=00 status=00',log)
        self.assertIn('matches_expected=NO matches_first=YES',log)
        self.assertEqual(self.writes(),3)
        readback=bytes((C.c_uint8*512).in_dll(self.lib,'wt_readback'))
        self.assertEqual(readback,bytes(508)+b'\xff'*4)
        self.assertEqual(binascii.crc_hqx(readback,0),0x99cf)
        after=self.image.read_bytes()
        self.assertEqual(before[:self.scratch*512],after[:self.scratch*512])
        self.assertEqual(before[(self.scratch+1)*512:],after[(self.scratch+1)*512:])
    def test_ff_corruption_only_after_faults_has_unambiguous_phase(self):
        self.lib.wt_host_config(25,2); self.lib.wt_host_config(22,224)
        C.c_int.in_dll(self.lib,'wt_crc_only').value=1
        result,log=self.suite_log()
        self.assertEqual(result,1); self.assertEqual(self.error(),105); self.assertTrue(self.poison())
        self.assertIn('phase=PRE-FAULT index=15 kind=MIXED',log)
        self.assertIn('phase=AFTER-COMMAND-CRC index=1 kind=FF',log)
        self.assertIn('RECOVERY: after=bad-command-CRC',log)
        self.assertNotIn('PROBE BEGIN: bad-data-CRC',log)
        self.assertNotIn('PHASE: FILESYSTEM',log)
        self.assertEqual(self.writes(),21)
        self.assertIn('differing_bytes=508',log)
        self.assertIn('repeat_valid=1 repeat_error=0',log)
    def test_normal_mode_avoids_faults_but_runs_full_filesystem_suite(self):
        self.lib.wt_host_config(25,2); self.lib.wt_host_config(11,1)
        C.c_int.in_dll(self.lib,'wt_normal_only').value=1
        result,log=self.suite_log(); self.assertEqual(result,0)
        self.assertIn('phase=PRE-FAULT index=15 kind=MIXED',log)
        self.assertNotIn('PHASE: FAULT-PROBES',log)
        self.assertNotIn('PHASE: POST-FAULT',log)
        self.assertIn('PHASE: FILESYSTEM',log); self.check_partition()
        before=self.digest(); self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.lib.wt_suite(0),0); self.assertEqual(before,self.digest())
    def test_probe_recovery_consumes_expected_crc_error_then_clean_status(self):
        self.arm(); before=self.digest(); self.lib.wt_host_config(26,128)
        self.assertEqual(self.lib.wt_bad_command(),0)
        self.assertEqual(self.lib.wt_recover(),0)
        self.assertEqual(list((C.c_uint*2).in_dll(self.lib,'wt_recovery_r1')),[8,0])
        self.assertEqual(list((C.c_uint*2).in_dll(self.lib,'wt_recovery_status')),[255,0])
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
        result,log=self.suite_log(); self.assertEqual(result,0)
        self.assertIn('R1=08 R2=FF (no R2 for command error)',log)
    def test_probe_recovery_never_hides_programming_status_error(self):
        self.lib.wt_host_config(26,32); result,log=self.suite_log()
        self.assertEqual(result,1); self.assertEqual(self.error(),104); self.assertTrue(self.poison())
        self.assertIn('RECOVERY STATUS: read=0 R1=00 R2=20',log)
        self.assertNotIn('PHASE: POST-FAULT',log); self.assertNotIn('PHASE: FILESYSTEM',log)
        self.assertEqual(self.writes(),18)
        before=self.digest(); self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_probe_recovery_timeout_and_repeated_r1_error_stop(self):
        self.arm(); self.lib.wt_host_config(19,14)
        self.assertLess(self.lib.wt_recover(),0); self.assertEqual(self.error(),101)
        self.assertTrue(self.poison()); self.lib.wt_host_config(19,0)
        self.assertEqual(self.lib.sd_init(),0); self.lib.wt_host_config(17,8)
        self.assertLess(self.lib.wt_recover(),0); self.assertEqual(self.error(),104)
        self.assertEqual(self.uint('wt_recovery_count'),2); self.assertTrue(self.poison())
    def select_probe(self, mode):
        C.c_int.in_dll(self.lib,'wt_probe_only').value=mode
    def test_command_only_probe_full_filesystem_and_persistence(self):
        self.select_probe(1); result,log=self.suite_log()
        self.assertEqual(result,0); self.assertIn('PROBE COMMAND:',log)
        self.assertIn('phase=AFTER-COMMAND-CRC index=15 kind=MIXED',log)
        self.assertNotIn('PROBE DATA RESULT:',log); self.assertNotIn('AFTER-DATA-CRC',log)
        self.check_partition(); before=self.digest(); self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.lib.wt_suite(0),0); self.assertEqual(before,self.digest())
    def test_data_only_probe_retains_rejection_trace_before_recovery(self):
        self.select_probe(2); self.lib.wt_host_config(28,4096); self.lib.wt_host_config(22,224)
        result,log=self.suite_log(); self.assertEqual(result,0)
        self.assertNotIn('PROBE COMMAND:',log)
        self.assertIn('PROBE DATA RESULT: return=-1 error=102 stage=324 poison=0',log)
        self.assertIn('data_CRC=0B3F calculated=0B3E CMD24_R1=00 response=EB',log)
        start=log.index('PROBE DATA RESULT:'); end=log.index('RECOVERY: after=bad-data-CRC',start)
        trace=log[start:end]
        self.assertIn('nonready_polls=4096',trace)
        self.assertIn('WRITE BUSY: entered=1',trace)
        self.assertIn('phase=AFTER-DATA-CRC index=15 kind=MIXED',log)
        self.check_partition()
    def test_command_crc_probe_does_not_accept_idle_plus_crc_error(self):
        self.lib.wt_host_close()
        self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),3),0)
        self.assertEqual(self.lib.sd_init(),0)
        self.lib.wt_select(0); self.lib.wt_select(1)
        self.lib.wt_io.argtypes=[C.c_uint8]; self.lib.wt_io.restype=C.c_uint8
        for value in bytes.fromhex('400000000095'): self.lib.wt_io(value)
        self.assertEqual(self.lib.wt_io(255),255); self.assertEqual(self.lib.wt_io(255),1)
        self.lib.wt_select(0)
        self.assertLess(self.lib.wt_bad_command(),0)
        self.assertEqual(self.uint('wt_bad_cmd_r1'),9)
        self.assertEqual(self.error(),102); self.assertEqual(self.writes(),0)
    def test_bad_command_trace_keeps_crc_r1_and_response_after_recovery(self):
        before=self.digest(); self.assertEqual(self.lib.wt_bad_command(),0)
        expected=self.lib.wt_crc7(bytes.fromhex('4d00000000'),5)
        self.assertEqual(self.uint('wt_bad_cmd_calculated'),expected)
        self.assertEqual(self.uint('wt_bad_cmd_crc'),expected^2)
        self.assertEqual(self.uint('wt_bad_cmd_r1'),8)
        n=self.uint('wt_bad_cmd_count')
        self.assertEqual(bytes((C.c_uint8*100).in_dll(self.lib,'wt_bad_cmd_response'))[:n],b'\xff\x08')
        self.assertEqual(self.lib.wt_recover(),0)
        self.assertEqual(self.uint('wt_bad_cmd_r1'),8); self.assertEqual(before,self.digest())
    def test_command_probe_read_timeout_isolated_and_poisoned(self):
        self.select_probe(1); self.lib.wt_host_config(27,1); before=self.digest()
        result,log=self.suite_log(); self.assertEqual(result,1); self.assertEqual(self.error(),101)
        self.assertTrue(self.poison()); self.assertEqual(self.writes(),18)
        self.assertIn('after=bad-command-CRC operation=read-original',log)
        self.assertIn('error=101 stage=17',log)
        self.assertNotIn('PROBE DATA RESULT:',log); self.assertNotIn('PHASE: FILESYSTEM',log)
        self.assertEqual(before,self.digest())
    def test_data_probe_read_timeout_reproduces_intenso_without_command_probe(self):
        self.select_probe(2); self.lib.wt_host_config(27,2); before=self.digest()
        result,log=self.suite_log(); self.assertEqual(result,1); self.assertEqual(self.error(),101)
        self.assertTrue(self.poison()); self.assertEqual(self.writes(),18)
        self.assertIn('PROBE DATA RESULT:',log); self.assertNotIn('PROBE COMMAND:',log)
        self.assertIn('after=bad-data-CRC operation=read-original',log)
        self.assertIn('error=101 stage=17',log); self.assertEqual(before,self.digest())
        self.assertIn('READ TOKEN TRACE:',log)
        self.assertEqual(self.uint('wt_packet_sample_count'),32)
        self.assertEqual(bytes((C.c_uint8*32).in_dll(self.lib,'wt_packet_tokens')),b'\xff'*32)
        self.assertGreater(C.c_uint32.in_dll(self.lib,'wt_packet_polls').value,32)
    def test_command_probe_accepted_discard_detected_before_data_probe(self):
        self.select_probe(1); self.lib.wt_host_config(27,3)
        result,log=self.suite_log(); self.assertEqual(result,1); self.assertEqual(self.error(),105)
        self.assertIn('PHASE: AFTER-COMMAND-CRC',log)
        self.assertIn('differing_bytes=512 matches_original_scratch=YES',log)
        self.assertNotIn('PROBE DATA RESULT:',log); self.assertEqual(self.writes(),19)
    def test_data_probe_accepted_discard_reproduces_sandisk(self):
        self.select_probe(2); self.lib.wt_host_config(27,4); self.lib.wt_host_config(22,224)
        result,log=self.suite_log(); self.assertEqual(result,1); self.assertEqual(self.error(),105)
        self.assertTrue(self.poison()); self.assertEqual(self.writes(),19)
        self.assertIn('PHASE: AFTER-DATA-CRC',log)
        self.assertIn('response=E5 CMD13_R1=00 status=00',log)
        self.assertIn('differing_bytes=512 matches_original_scratch=YES',log)
        self.assertIn('matches_expected=NO matches_first=YES',log)
        self.assertNotIn('PROBE COMMAND:',log); self.assertNotIn('PHASE: FILESYSTEM',log)
    def test_other_probe_fault_cannot_contaminate_isolated_mode(self):
        for mode,fault in ((1,2),(2,1)):
            self.lib.wt_host_close(); self.layout=builder.prepare(self.image)
            self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),1),0)
            self.assertEqual(self.lib.sd_init(),0); self.select_probe(mode)
            self.lib.wt_host_config(27,fault)
            result,log=self.suite_log(); self.assertEqual(result,0); self.check_partition()
    def test_rejected_data_busy_is_completed_before_cs_release(self):
        self.select_probe(2); self.lib.wt_host_config(27,7); self.lib.wt_host_config(28,64)
        result,log=self.suite_log(); self.assertEqual(result,0)
        self.assertIn('PROBE DATA RESULT: return=-1 error=102 stage=324 poison=0',log)
        self.assertIn('nonready_polls=64',log); self.check_partition()
    def test_rejected_data_busy_timeout_stops_without_recovery_or_writes(self):
        self.select_probe(2); self.lib.wt_host_config(28,0xffffffff)
        before=self.digest(); result,log=self.suite_log()
        self.assertEqual(result,1); self.assertEqual(self.error(),101); self.assertTrue(self.poison())
        self.assertIn('error=101 stage=324 poison=1',log)
        self.assertNotIn('RECOVERY: after=bad-data-CRC',log)
        self.assertEqual(self.writes(),18); self.assertEqual(before,self.digest())
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_nonzero_original_scratch_still_requires_changing_seed(self):
        with self.image.open('r+b') as f: f.seek(self.scratch*512); f.write(b'\x96'*512)
        self.select_probe(2); result,log=self.suite_log(); self.assertEqual(result,0)
        self.assertIn('PASS: seed 96 before post-probe raw patterns',log)
        self.check_partition()
        with self.image.open('rb') as f: f.seek(self.scratch*512); self.assertEqual(f.read(512),b'\x96'*512)
    def test_progress_reports_large_file_writes_and_verification(self):
        C.c_int.in_dll(self.lib,'wt_normal_only').value=1
        result,log=self.suite_log(); self.assertEqual(result,0)
        for size in (4096,32768,65536,70000):
            self.assertIn('PROGRESS: append bytes='+str(size)+'/70000',log)
        self.assertIn('PROGRESS: verify WTEST\\BIG.BIN bytes=70000/70000',log)
    def test_crc_valid_changed_post_probe_read_is_not_reported_as_timeout(self):
        self.select_probe(2); self.lib.wt_host_config(27,6); before=self.digest()
        result,log=self.suite_log(); self.assertEqual(result,1)
        self.assertEqual(self.error(),105); self.assertTrue(self.poison())
        self.assertIn('HEX saved-original 000: 00',log)
        self.assertIn('HEX post-probe 000: 01',log)
        self.assertNotIn('PHASE: FILESYSTEM',log); self.assertEqual(before,self.digest())
    def test_crc_independent_oracle(self):
        for data in (b'',b'123456789',bytes(512),b'\xff'*512,
                     bytes(range(256))*2,bytes((i*37+(i>>3))&255 for i in range(512))):
            with self.subTest(length=len(data),prefix=data[:8]):
                self.assertEqual(self.lib.wt_crc16(data,len(data)),binascii.crc_hqx(data,0))
        # Independent polynomial division, rather than the C shift-feedback algorithm.
        for data in (bytes.fromhex('4000000000'),bytes.fromhex('48000001aa'),
                     bytes.fromhex('5800000808'),bytes.fromhex('7b00000001')):
            dividend=int.from_bytes(data,'big')<<7
            for bit in range(len(data)*8+6,6,-1):
                if dividend & (1<<bit): dividend ^= 0x89 << (bit-7)
            self.assertEqual(self.lib.wt_crc7(data,len(data)),(dividend<<1)|1)
    def test_register_rejections_report_nonzero_error(self):
        before=self.digest()
        for command in (9,10):
            with self.subTest(command=command):
                self.lib.wt_host_config(18,command+1)
                self.assertLess(self.lib.sd_init(),0); self.assertEqual(self.error(),103)
                self.assertEqual(self.uint('wt_stage'),command)
                self.assertEqual(self.uint('wt_r1'),4)
                self.assertEqual(C.c_int.in_dll(self.lib,'wt_host_selected').value,0)
                self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_missing_initialization_response_preserves_timeout(self):
        for command in (8,55,58,59,9,10):
            with self.subTest(command=command):
                self.lib.wt_host_config(19,command+1)
                self.assertLess(self.lib.sd_init(),0); self.assertEqual(self.error(),101)
                self.assertEqual(self.uint('wt_stage'),command)
                self.assertEqual(C.c_int.in_dll(self.lib,'wt_host_selected').value,0)
                self.assertEqual(self.writes(),0)
    def test_read_token_delay_and_rejection(self):
        before=self.digest(); self.lib.wt_host_config(13,4096)
        self.assertEqual(self.lib.sd_read(self.scratch,self.buffer),0)
        for mode,error in ((1,101),(2,103)):
            self.lib.wt_host_config(14,mode)
            self.assertLess(self.lib.sd_read(self.scratch,self.buffer),0)
            self.assertEqual(self.error(),error)
            self.assertEqual(C.c_int.in_dll(self.lib,'wt_host_selected').value,0)
            self.assertEqual(before,self.digest()); self.assertEqual(self.writes(),0)
    def test_read_timeout_wrap_and_frozen_clock(self):
        self.lib.wt_host_clock.argtypes=[C.c_uint,C.c_int]
        self.lib.wt_host_config(14,1)
        for base,frozen in ((65530,0),(65530,1)):
            self.lib.wt_host_clock(base,frozen)
            self.assertLess(self.lib.sd_read(self.scratch,self.buffer),0)
            self.assertEqual(self.error(),101)
            self.assertEqual(C.c_int.in_dll(self.lib,'wt_host_selected').value,0)
    def test_write_response_delay_and_late_busy(self):
        self.arm(); self.lib.wt_host_config(16,25)
        self.lib.wt_host_config(1,4096); self.lib.wt_host_config(20,3)
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.uint('wt_response_count'),27)
        self.assertEqual(self.uint('wt_write_token'),5)
        self.assertGreater(C.c_uint32.in_dll(self.lib,'wt_busy_max').value,0)
        self.assertEqual(self.writes(),1)
    def test_missing_and_invalid_write_response_poison(self):
        for mode,error in ((1,101),(2,103)):
            with self.subTest(mode=mode):
                self.lib.wt_host_close()
                self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),1),0)
                self.assertEqual(self.lib.sd_init(),0); self.arm()
                self.lib.wt_host_config(15,mode)
                self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
                self.assertEqual(self.error(),error); self.assertEqual(self.poison(),1)
                self.assertEqual(self.writes(),0) # No acceptance was observed, despite model commit.
                self.assertEqual(C.c_int.in_dll(self.lib,'wt_host_selected').value,0)
                before=self.digest()
                self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
                self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_program_status_r1_rejection_poison(self):
        self.arm(); self.lib.wt_host_config(17,4)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),104); self.assertEqual(self.poison(),1)
        self.assertEqual(self.uint('wt_program_r1'),4); self.assertEqual(self.writes(),1)
    def test_repeat_crc_failure_preserves_first_mismatch(self):
        self.arm(); self.lib.wt_host_config(12,1); self.lib.wt_host_config(21,1)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),105); self.assertEqual(self.poison(),1)
        self.assertEqual(self.uint('wt_readback_valid'),1)
        self.assertEqual(self.uint('wt_repeat_valid'),0); self.assertEqual(self.uint('wt_repeat_error'),102)
        self.assertEqual(self.uint('wt_write_token'),5); self.assertEqual(self.uint('wt_program_status'),0)
        self.assertEqual(self.uint('wt_stage'),17); self.assertEqual(self.writes(),1)
        self.assertEqual(bytes((C.c_ubyte*512).in_dll(self.lib,'wt_readback'))[0],1)
        before=self.digest(); self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_marker_transport_crc_error_preserved(self):
        for lba in (self.layout['data'],self.layout['data']+1498):
            with self.subTest(lba=lba):
                self.lib.wt_host_config(10,lba)
                self.assertLess(self.lib.wf_prepare(),0); self.assertEqual(self.error(),102)
                self.assertEqual(self.writes(),0)
                self.assertEqual(self.uint('wt_packet_complete'),1)
                self.assertEqual(self.uint('wt_packet_count'),512)
                self.assertNotEqual(self.uint('wt_packet_crc'),self.uint('wt_packet_calculated'))
    def test_crc_failure_log_retains_untrusted_payload(self):
        self.lib.wt_host_config(10,2055)
        result,log=self.diag_log(); self.assertEqual(result,1)
        self.assertIn('READ CRC: clocked_bytes=512 received=',log)
        self.assertIn('payload=UNTRUSTED',log); self.assertIn('HEX untrusted 496:',log)
    def test_empty_file_with_cluster_reports_verify_error(self):
        self.assertEqual(self.lib.wt_suite(1),0)
        entry=C.create_string_buffer(32)
        self.assertEqual(self.lib.fs_lookup(b'WTEST',entry),0)
        first=struct.unpack_from('<H',entry.raw,26)[0]|(struct.unpack_from('<H',entry.raw,20)[0]<<16)
        sector=self.layout['data']+first-2
        with self.image.open('r+b') as f:
            f.seek(sector*512); directory=f.read(512)
            offset=directory.index(b'Z0      BIN')
            f.seek(sector*512+offset+26); f.write(struct.pack('<H',2))
        self.lib.wt_test_verify_file.argtypes=[C.c_char_p,C.c_uint32,C.c_uint]
        before=self.digest()
        self.assertLess(self.lib.wt_test_verify_file(b'WTEST\\Z0.BIN',0,3),0)
        self.assertEqual(self.error(),105); self.assertEqual(before,self.digest())
    def test_protected_fixture_mismatch_reports_verify_error(self):
        self.assertEqual(self.lib.wf_prepare(),0)
        entry=C.create_string_buffer(32); self.assertEqual(self.lib.fs_lookup(b'README.TXT',entry),0)
        first=struct.unpack_from('<H',entry.raw,26)[0]|(struct.unpack_from('<H',entry.raw,20)[0]<<16)
        with self.image.open('r+b') as f:
            f.seek((self.layout['data']+first-2)*512); f.write(b'X')
        before=self.digest()
        self.assertEqual(self.lib.wt_suite(0),1)
        self.assertEqual(self.error(),105); self.assertEqual(self.writes(),0)
        self.assertEqual(before,self.digest())
    def test_uncertain_bad_crc_probe_poisoned(self):
        self.arm(); self.assertEqual(self.lib.wt_crc_mode(0),0)
        self.lib.wt_host_config(15,1)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,1),0)
        self.assertEqual(self.error(),101); self.assertEqual(self.poison(),1)
        before=self.digest(); self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_crc_off_valid_control_uses_same_readback_mode(self):
        self.arm(); self.assertEqual(self.lib.wt_crc_mode(0),0)
        self.buffer.raw=b'\x96'*512
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.uint('wt_write_crc'),0)
        self.assertEqual(self.uint('wt_readback_crc'),1)
        self.assertEqual(self.uint('wt_sent_crc'),self.uint('wt_calculated_crc'))
        self.assertEqual(self.uint('wt_readback_valid'),1)
        self.assertEqual(self.writes(),1)
    def test_crc_off_bad_only_discard_distinguished_from_control_failure(self):
        self.lib.wt_host_config(11,2); self.lib.wt_host_config(22,224)
        self.lib.wt_test_log.argtypes=[C.c_char_p]; path=self.work/'bad-only.log'
        self.lib.wt_test_log(str(path).encode())
        try: self.assertEqual(self.lib.wt_suite(1),1)
        finally: self.lib.wt_test_log(None)
        log=path.read_text()
        self.assertIn('PASS: CRC-OFF valid-data-CRC control',log)
        self.assertIn('PASS: restore scratch before CRC-OFF invalid-data-CRC probe',log)
        self.assertIn('PROBE: CRC-OFF with INVALID data CRC',log)
        self.assertIn('FAIL: CRC-disabled diagnostic produced an unexpected failure',log)
        self.assertIn('CRC_mode=OFF data_CRC=0B3F calculated=0B3E',log)
        self.assertIn('response=E5 CMD13_R1=00 status=00',log)
        self.assertIn('matches_original_scratch=YES repeat_valid=1',log)
        self.assertIn('WRITE BUSY:',log); self.assertIn('STATUS READY:',log)
        self.assertEqual(self.writes(),57); self.assertEqual(self.error(),105)
        self.assertEqual(self.poison(),1)
        self.assertEqual(C.c_uint32.in_dll(self.lib,'wf_allocated').value,0)
        before=self.digest(); self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_write_busy_trace_is_per_write_and_resets(self):
        self.arm(); self.lib.wt_host_config(1,4096)
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.uint('wt_busy_entered'),1); self.assertEqual(self.uint('wt_status_entered'),1)
        self.assertEqual(C.c_uint32.in_dll(self.lib,'wt_write_busy_polls').value,4096)
        self.assertEqual(C.c_uint32.in_dll(self.lib,'wt_status_busy_polls').value,0)
        self.assertEqual(self.uint('wt_busy_sample_count'),32)
        self.assertEqual(bytes((C.c_ubyte*32).in_dll(self.lib,'wt_busy_samples')),bytes(32))
        self.lib.wt_host_config(1,0)
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(C.c_uint32.in_dll(self.lib,'wt_write_busy_polls').value,0)
        self.assertEqual(self.uint('wt_busy_sample_count'),2)
        self.assertEqual((C.c_ubyte*32).in_dll(self.lib,'wt_busy_samples')[0],255)
    def test_late_busy_trace_captures_status_ready_wait(self):
        self.arm(); self.lib.wt_host_config(1,4096); self.lib.wt_host_config(20,3)
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(C.c_uint32.in_dll(self.lib,'wt_write_busy_polls').value,0)
        self.assertGreater(C.c_uint32.in_dll(self.lib,'wt_status_busy_polls').value,0)
        self.assertEqual((C.c_ubyte*32).in_dll(self.lib,'wt_busy_samples')[0],255)
        self.assertEqual((C.c_ubyte*32).in_dll(self.lib,'wt_status_samples')[0],0)
    def test_busy_timeout_trace_retained_and_status_not_entered(self):
        self.arm(); self.lib.wt_host_config(3,1)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),101); self.assertEqual(self.poison(),1)
        self.assertEqual(self.uint('wt_busy_entered'),1); self.assertEqual(self.uint('wt_status_entered'),0)
        self.assertGreaterEqual(C.c_uint32.in_dll(self.lib,'wt_write_busy_ticks').value,90)
        self.assertEqual(self.uint('wt_busy_sample_count'),32)
        self.assertEqual(self.uint('wt_status_sample_count'),0)
    def test_data_response_undefined_high_bits_accept_e5(self):
        self.arm(); self.lib.wt_host_config(22,224)
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.uint('wt_write_token'),0xe5)
        self.assertEqual(self.uint('wt_readback_valid'),1)
    def test_late_busy_does_not_hide_programming_error(self):
        self.arm(); self.lib.wt_host_config(1,4096); self.lib.wt_host_config(20,3)
        self.lib.wt_host_config(5,1)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),104); self.assertEqual(self.poison(),1)
        self.assertEqual(self.uint('wt_program_r1'),0); self.assertEqual(self.uint('wt_program_status'),0x20)
        self.assertEqual(self.uint('wt_cmd13_rx_count'),6)
        self.assertEqual(bytes((C.c_ubyte*6).in_dll(self.lib,'wt_cmd13_rx')),b'\xff'*6)
        self.assertEqual(self.uint('wt_readback_valid'),0)
    def test_busy_during_cmd13_transmission_is_safe_stop(self):
        self.arm(); self.lib.wt_host_config(1,4096); self.lib.wt_host_config(20,4)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),101); self.assertEqual(self.poison(),1)
        self.assertEqual(self.uint('wt_stage'),13); self.assertEqual(self.uint('wt_program_r1'),255)
        self.assertEqual(self.uint('wt_cmd13_rx_count'),1)
        self.assertEqual((C.c_ubyte*6).in_dll(self.lib,'wt_cmd13_rx')[0],0)
        self.assertEqual(self.uint('wt_readback_valid'),0)
        before=self.digest(); self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_cold_start_initializes_board_and_idle_clocks(self):
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_host_pull_high_calls').value,1)
        self.assertGreaterEqual(C.c_uint.in_dll(self.lib,'wt_host_startup_clocks').value,12)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_reset_attempts').value,1)
        self.assertEqual(self.writes(),0)
    def test_cold_start_retries_unanswered_cmd0(self):
        before=self.digest(); self.lib.wt_host_config(9,3)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_reset_attempts').value,4)
        self.assertEqual(self.error(),0); self.assertEqual(self.writes(),0)
        self.assertEqual(before,self.digest())
    def test_cold_start_retry_limit_stops_without_writes(self):
        before=self.digest(); self.lib.wt_host_config(9,1000)
        self.assertLess(self.lib.sd_init(),0)
        self.assertEqual(self.error(),106)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_stage').value,0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_r1').value,255)
        self.assertLessEqual(C.c_uint.in_dll(self.lib,'wt_reset_attempts').value,100)
        self.assertEqual(C.c_int.in_dll(self.lib,'wt_host_selected').value,0)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def diag_log(self):
        self.lib.wt_test_log.argtypes=[C.c_char_p]
        path=self.work/'diag.log'; before=self.digest()
        self.lib.wt_test_log(str(path).encode())
        try: result=self.lib.wt_diagnose()
        finally: self.lib.wt_test_log(None)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),107)
        return result,path.read_text()
    def test_diagnostic_clean_image_is_read_only(self):
        result,log=self.diag_log(); self.assertEqual(result,0)
        self.assertIn('FSINFO primary:',log); self.assertIn('FSINFO backup:',log)
        self.assertEqual(log.count('signatures=valid'),2)
        self.assertEqual(log.count('differing_bytes=0'),2)
        self.assertIn('HEX backup 496:',log)
    def test_diagnostic_fsinfo_hint_mismatch_is_precise(self):
        with self.image.open('r+b') as f:
            f.seek(2055*512+488); f.write(struct.pack('<I',0xffffffff))
        result,log=self.diag_log(); self.assertEqual(result,1)
        self.assertIn('PREFLIGHT: FSInfo primary/backup byte equality',log)
        self.assertIn('DIFF: offset=488',log); self.assertIn('other_bytes=0',log)
        self.assertEqual(log.count('signatures=valid'),2)
    def test_diagnostic_invalid_identical_fsinfo_signatures(self):
        with self.image.open('r+b') as f:
            for sector in (2049,2055): f.seek(sector*512); f.write(b'BAD!')
        result,log=self.diag_log(); self.assertEqual(result,1)
        self.assertIn('PREFLIGHT: FSInfo signatures',log)
        self.assertEqual(log.count('signatures=INVALID'),2)
    def test_diagnostic_backup_crc_error_is_not_safety_error(self):
        self.lib.wt_host_config(10,2055)
        self.assertLess(self.lib.wf_prepare(),0); self.assertEqual(self.error(),102)
        reason=C.c_char_p.in_dll(self.lib,'wf_preflight').value
        self.assertEqual(reason,b'FSInfo backup read')
        result,log=self.diag_log(); self.assertEqual(result,1)
        self.assertIn('error=102 stage=17 LBA=2055',log)
        self.assertIn('failed reads are not compared',log)
        self.assertNotIn('FSINFO backup:',log)
    def test_diagnostic_boot_mismatch_and_missing_marker(self):
        with self.image.open('r+b') as f: f.seek(2054*512+3); f.write(b'BADBOOT!')
        result,log=self.diag_log(); self.assertEqual(result,1)
        self.assertIn('PREFLIGHT: boot primary/backup byte equality',log)
        self.assertIn('DIFF: offset=3',log)
        self.assertIn('FSINFO primary:',log)
    def allow_hints(self): C.c_int.in_dll(self.lib,'wf_allow_hints').value=1
    def test_allow_hints_full_write_suite_and_checker(self):
        with self.image.open('r+b') as f:
            f.seek(2055*512+488); f.write(struct.pack('<II',0xffffffff,66000))
        before=self.digest(); self.assertLess(self.lib.wf_prepare(),0)
        self.assertEqual(C.c_int.in_dll(self.lib,'wf_hint_mismatch').value,1)
        self.assertEqual(before,self.digest()); self.allow_hints()
        self.assertEqual(self.lib.wt_suite(1),0); self.check_partition()
        with self.image.open('rb') as f:
            f.seek(2049*512); primary=f.read(512)
            f.seek(2055*512); backup=f.read(512)
        self.assertEqual(primary,backup)
        self.assertEqual(primary[488:496],b'\xff'*8)
    def test_allow_hints_cannot_bypass_read_crc_error(self):
        self.allow_hints(); self.lib.wt_host_config(10,2055); before=self.digest()
        self.assertLess(self.lib.wf_prepare(),0); self.assertEqual(self.error(),102)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_allow_hints_cannot_bypass_nonhint_difference(self):
        self.allow_hints()
        with self.image.open('r+b') as f: f.seek(2055*512+100); f.write(b'X')
        before=self.digest(); self.assertLess(self.lib.wf_prepare(),0)
        self.assertEqual(self.error(),107); self.assertEqual(self.writes(),0)
        self.assertEqual(C.c_int.in_dll(self.lib,'wf_hint_mismatch').value,0)
        self.assertEqual(before,self.digest())
    def test_allow_hints_cannot_bypass_invalid_signature(self):
        self.allow_hints()
        with self.image.open('r+b') as f: f.seek(2055*512); f.write(b'BAD!')
        before=self.digest(); self.assertLess(self.lib.wf_prepare(),0)
        self.assertEqual(self.error(),107); self.assertEqual(self.writes(),0)
        self.assertEqual(before,self.digest())
    def test_allow_hints_cannot_bypass_boot_fat_or_marker(self):
        for offset,value in [(2054*512+3,b'BADBOOT!'),((2048+32+547)*512+20,b'BAD!'),
                             ((self.layout['data']+1498)*512,b'WRONG')]:
            with self.subTest(offset=offset):
                self.lib.wt_host_close(); self.layout=builder.prepare(self.image)
                self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),1),0)
                self.assertEqual(self.lib.sd_init(),0); self.allow_hints()
                with self.image.open('r+b') as f: f.seek(offset); f.write(value)
                before=self.digest(); self.assertLess(self.lib.wf_prepare(),0)
                self.assertEqual(self.error(),107); self.assertEqual(self.writes(),0)
                self.assertEqual(before,self.digest())
    def reopen_cold(self, delay=0):
        self.lib.wt_host_close()
        self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),9),0)
        self.lib.wt_host_timing.argtypes=[C.c_uint]
        self.lib.wt_host_timing(delay)
    def test_native_nonready_card_receives_reset_and_warm_restart(self):
        self.reopen_cold(); before=self.digest()
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_startup_miso').value,0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_cmd0_sent').value,1)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_reset_attempts').value,1)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_host_idle_repeats').value,12)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_startup_miso').value,255)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_native_card_delayed_byte_completion_reads_and_writes(self):
        self.reopen_cold(delay=3)
        self.assertEqual(self.lib.sd_init(),0); self.arm()
        self.buffer.raw=bytes(i%251 for i in range(512))
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        out=C.create_string_buffer(512)
        self.assertEqual(self.lib.sd_read(self.scratch,out),0)
        self.assertEqual(out.raw,self.buffer.raw)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_host_unfinished').value,0)
    def test_native_nonready_without_reset_response_stops_bounded(self):
        self.reopen_cold(); before=self.digest(); self.lib.wt_host_config(9,1000)
        self.assertLess(self.lib.sd_init(),0); self.assertEqual(self.error(),106)
        self.assertGreater(C.c_uint.in_dll(self.lib,'wt_cmd0_sent').value,0)
        self.assertLessEqual(C.c_uint.in_dll(self.lib,'wt_cmd0_sent').value,100)
        self.assertEqual(C.c_int.in_dll(self.lib,'wt_host_selected').value,0)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def set_nocrc(self):
        C.c_int.in_dll(self.lib,'wt_no_crc').value=1
        self.assertEqual(self.lib.sd_init(),0)
    def test_nocrc_full_suite_persistence_and_checker(self):
        self.set_nocrc(); self.assertEqual(self.lib.wt_suite(1),0)
        self.check_partition(); before=self.digest()
        self.assertEqual(self.lib.sd_init(),0); self.assertEqual(self.lib.wt_suite(0),0)
        self.assertEqual(before,self.digest())
    def test_nocrc_init_without_cmd59_and_dummy_data_crc(self):
        self.lib.wt_host_config(6,1); self.set_nocrc(); self.arm()
        self.buffer.raw=b'X'*512
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_sent_crc').value,0xffff)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_write_crc').value,0)
    def test_nocrc_strict_card_refuses_dummy_crc_and_stops(self):
        self.lib.wt_host_close()
        self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),11),0)
        self.set_nocrc(); self.arm(); self.buffer.raw=b'X'*512; before=self.digest()
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),102); self.assertTrue(self.poison())
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_write_token').value&31,11)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_nocrc_still_checks_read_crc(self):
        self.set_nocrc(); self.lib.wt_host_config(4,1)
        self.assertLess(self.lib.sd_read(0,self.buffer),0); self.assertEqual(self.error(),102)
        self.assertEqual(self.writes(),0)
    def test_crconly_does_not_attempt_crc_off_probe(self):
        self.lib.wt_host_config(11,1)
        C.c_int.in_dll(self.lib,'wt_crc_only').value=1
        self.assertEqual(self.lib.wt_suite(1),0); self.check_partition()
    def test_accepted_ignored_off_write_has_exact_diagnostics(self):
        self.lib.wt_host_config(11,1)
        self.lib.wt_test_log.argtypes=[C.c_char_p]; path=self.work/'failed-write.log'
        self.lib.wt_test_log(str(path).encode())
        try: self.assertEqual(self.lib.wt_suite(1),1)
        finally: self.lib.wt_test_log(None)
        self.assertEqual(self.error(),105); self.assertTrue(self.poison())
        log=path.read_text()
        self.assertIn('response=05 CMD13_R1=00 status=00',log)
        self.assertIn('FAIL: CRC-OFF valid-data-CRC control',log)
        self.assertNotIn('PROBE: CRC-OFF with INVALID data CRC',log)
        self.assertIn('matches_original_scratch=YES',log)
        self.assertIn('repeat_valid=1 repeat_error=0',log)
        self.assertIn('REPEAT: matches_expected=NO matches_first=YES',log)
        self.assertIn('HEX expected 496:',log); self.assertIn('HEX readback 496:',log)
        self.assertIn('HEX repeat 496:',log)
        self.assertEqual(self.writes(),55) # 18 PRE plus 18 per isolated probe, then discarded OFF control
        before=self.digest(); self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(before,self.digest())
    def test_nocrc_corrupt_readback_preserves_first_failure(self):
        self.set_nocrc(); self.arm(); self.buffer.raw=b'X'*512
        self.lib.wt_host_config(8,1)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),105); self.assertTrue(self.poison())
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_readback_valid').value,1)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_repeat_valid').value,1)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_write_token').value,5)
        self.assertEqual(C.c_uint.in_dll(self.lib,'wt_program_status').value,0)
    def test_repeat_matching_expected_never_clears_first_failure(self):
        self.set_nocrc(); self.arm(); self.buffer.raw=b'X'*512
        self.lib.wt_host_config(12,1)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),105); self.assertTrue(self.poison())
        self.assertEqual(self.writes(),1)
        first=bytes((C.c_uint8*512).in_dll(self.lib,'wt_readback'))
        repeat=bytes((C.c_uint8*512).in_dll(self.lib,'wt_repeat'))
        self.assertNotEqual(first,self.buffer.raw); self.assertEqual(repeat,self.buffer.raw)
    def test_nocrc_faults_preserve_stop_policy(self):
        for option,expected,changed in [(2,103,False),(3,101,True),(5,104,True),(4,102,True)]:
            with self.subTest(option=option):
                self.lib.wt_host_close(); self.layout=builder.prepare(self.image)
                self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),9),0)
                self.set_nocrc(); self.fault_write(option,expected,changed)
    def test_crc_vectors(self):
        self.assertEqual(self.lib.wt_crc7(b'\x40\0\0\0\0',5),0x95)
        self.assertEqual(self.lib.wt_crc7(b'\x48\0\0\x01\xaa',5),0x87)
        self.assertEqual(self.lib.wt_crc16(b'123456789',9),0x31c3)
    def test_failing_local_log_disarms_writes(self):
        self.lib.wt_test_log.argtypes=[C.c_char_p]
        before=self.digest(); self.lib.wt_test_log(b'/dev/full')
        try:
            self.assertEqual(self.lib.wt_suite(1),2)
            self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
        finally: self.lib.wt_test_log(None)
    def test_info_is_read_only(self):
        before=self.digest(); self.assertEqual(self.lib.wf_prepare(),0)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_write_fence_without_arm(self):
        before=self.digest(); self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),107); self.assertEqual(before,self.digest())
        self.arm(); self.assertLess(self.lib.wt_write(self.scratch+1,self.buffer,0),0)
        self.assertLess(self.lib.wt_write(0,self.buffer,0),0); self.assertEqual(before,self.digest())
    def test_valid_write_and_busy(self):
        self.arm(); self.lib.wt_host_config(1,4096)
        self.buffer.raw=bytes(i%251 for i in range(512))
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,0),0)
        out=C.create_string_buffer(512); self.assertEqual(self.lib.sd_read(self.scratch,out),0)
        self.assertEqual(out.raw,self.buffer.raw)
        self.assertGreater(C.c_uint32.in_dll(self.lib,'wt_busy_max').value,0)
    def test_crc_reject_changes_nothing(self):
        self.arm(); before=self.digest()
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,1),0)
        self.assertEqual(self.error(),102); self.assertFalse(self.poison()); self.assertEqual(before,self.digest())
        self.assertEqual(self.lib.wt_bad_command(),0)
    def test_tolerant_card_crc_disabled(self):
        self.arm(); self.assertEqual(self.lib.wt_crc_mode(0),0)
        self.assertEqual(self.lib.wt_write(self.scratch,self.buffer,1),0)
        self.assertEqual(self.lib.wt_crc_mode(1),0)
    def test_strict_card_even_with_crc_disabled(self):
        self.lib.wt_host_close(); self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),7),0)
        self.assertEqual(self.lib.sd_init(),0); self.arm(); self.assertEqual(self.lib.wt_crc_mode(0),0)
        before=self.digest(); self.assertLess(self.lib.wt_write(self.scratch,self.buffer,1),0)
        self.assertEqual(self.error(),102); self.assertEqual(before,self.digest())
    def fault_write(self,option,expected,changed):
        self.arm(); self.buffer.raw=b'\x96'*512; before=self.digest()
        self.lib.wt_host_config(option,1)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),expected); self.assertTrue(self.poison())
        after=self.digest(); self.assertEqual(before!=after,changed)
        self.assertLess(self.lib.wt_write(self.scratch,self.buffer,0),0)
        self.assertEqual(self.error(),111); self.assertEqual(after,self.digest())
        self.assertEqual(C.c_int.in_dll(self.lib,'wt_host_selected').value,0)
    def test_rejection_stops_session(self): self.fault_write(2,103,False)
    def test_accepted_busy_timeout_never_retries(self): self.fault_write(3,101,True)
    def test_delayed_programming_error_stops(self): self.fault_write(5,104,True)
    def test_corrupt_readback_stops(self): self.fault_write(8,105,True)
    def test_removal_after_acceptance_stops(self): self.fault_write(7,101,True)
    def test_readback_crc_error_stops(self): self.fault_write(4,102,True)
    def test_read_crc_error(self):
        self.lib.wt_host_config(4,1); self.assertLess(self.lib.sd_read(0,self.buffer),0)
        self.assertEqual(self.error(),102)
    def test_unsupported_crc_enable_refuses(self):
        self.lib.wt_host_config(6,1); self.assertLess(self.lib.sd_init(),0)
        self.assertEqual(self.error(),102); self.assertEqual(self.writes(),0)
    def test_wrong_tag_never_writes(self):
        with self.image.open('r+b') as f: f.seek((self.layout['data']+1498)*512); f.write(b'WRONG')
        before=self.digest(); self.assertLess(self.lib.wf_prepare(),0)
        self.assertEqual(self.error(),107); self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_mirror_mismatch_never_writes(self):
        with self.image.open('r+b') as f: f.seek((2048+32+547)*512+20); f.write(b'BAD!')
        before=self.digest(); self.assertLess(self.lib.wf_prepare(),0)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_metadata_mirror_failure_stops(self):
        d=self.begin(); before=self.writes(); self.lib.wt_host_config(2,2)
        f=WFile()
        self.assertLess(self.lib.wf_mkdir(d.first,b'BAD',C.byref(f)),0)
        self.assertTrue(self.poison()); count=self.writes(); self.assertEqual(count,before+1)
        self.assertLess(self.lib.wf_mkdir(d.first,b'AGAIN',C.byref(f)),0); self.assertEqual(self.writes(),count)
    def test_invalid_paths_and_duplicate(self):
        d=self.begin(); f=WFile()
        self.assertLess(self.lib.wf_create(2,b'OUTSIDE.BIN',C.byref(f)),0); self.assertEqual(self.error(),107)
        self.assertLess(self.lib.wf_create(d.first,b'..',C.byref(f)),0)
        self.assertEqual(self.lib.wf_create(d.first,b'ONE.BIN',C.byref(f)),0)
        writes=self.writes(); self.assertLess(self.lib.wf_create(d.first,b'ONE.BIN',C.byref(f)),0)
        self.assertEqual(self.error(),109); self.assertEqual(self.writes(),writes)
    def test_partial_append_overwrite_truncate_delete(self):
        d=self.begin(); f=WFile(); self.assertEqual(self.lib.wf_create(d.first,b'FILE.BIN',C.byref(f)),0)
        self.assertEqual(self.lib.wf_append(C.byref(f),b'A'*511,511),0)
        self.assertEqual(self.lib.wf_append(C.byref(f),b'B'*514,514),0)
        self.assertEqual(f.size,1025); self.assertEqual(self.lib.wf_overwrite(C.byref(f),510,b'XYZ',3),0)
        self.assertEqual(self.lib.wf_truncate(C.byref(f),512),0)
        self.assertEqual(self.lib.wf_truncate(C.byref(f),0),0)
        self.assertEqual(self.lib.wf_append(C.byref(f),b'Z',1),0)
        self.assertEqual(self.lib.wf_delete(C.byref(f)),0); self.assertEqual(self.lib.wf_finish(),0); self.check_partition()
    def test_full_volume_cannot_allocate_or_extend(self):
        d=self.begin(); f=WFile(); self.assertEqual(self.lib.wf_create(d.first,b'FULL.BIN',C.byref(f)),0)
        with self.image.open('r+b') as disk:
            disk.seek((2048+32)*512); fat=bytearray(disk.read(547*512))
            for c in range(2,70002):
                if struct.unpack_from('<I',fat,c*4)[0]==0: struct.pack_into('<I',fat,c*4,0x0ffffff7)
            for lba in (2048+32,2048+32+547): disk.seek(lba*512); disk.write(fat)
        before=self.digest(); writes=self.writes()
        self.assertLess(self.lib.wf_append(C.byref(f),b'A',1),0)
        self.assertEqual(self.error(),108); self.assertEqual(f.size,0)
        self.assertEqual(writes,self.writes()); self.assertEqual(before,self.digest())
    def test_empty_read_and_size_clamp(self):
        d=self.begin(); f=WFile(); self.assertEqual(self.lib.wf_create(d.first,b'EOF.BIN',C.byref(f)),0)
        self.lib.wf_read.argtypes=[C.POINTER(WFile),C.c_uint32,C.c_void_p,C.c_uint16,C.POINTER(C.c_uint16)]
        n=C.c_uint16(999); self.assertEqual(self.lib.wf_read(C.byref(f),0,self.buffer,512,C.byref(n)),0)
        self.assertEqual(n.value,0)
        self.assertEqual(self.lib.wf_append(C.byref(f),b'ABC',3),0)
        self.assertEqual(self.lib.wf_read(C.byref(f),1,self.buffer,512,C.byref(n)),0)
        self.assertEqual(n.value,2); self.assertEqual(self.buffer.raw[:2],b'BC')
        self.assertEqual(self.lib.wf_read(C.byref(f),3,self.buffer,512,C.byref(n)),0); self.assertEqual(n.value,0)
    def test_corrupt_file_chain_refuses_mutation(self):
        d=self.begin(); f=WFile(); self.assertEqual(self.lib.wf_create(d.first,b'LOOP.BIN',C.byref(f)),0)
        self.assertEqual(self.lib.wf_append(C.byref(f),b'A'*512,512),0)
        for value in (f.first,0):
            with self.image.open('r+b') as disk:
                for base in (2048+32,2048+32+547):
                    disk.seek(base*512+f.first*4); disk.write(struct.pack('<I',value))
            before=self.digest(); count=self.writes()
            self.assertLess(self.lib.wf_delete(C.byref(f)),0); self.assertEqual(self.error(),107)
            self.assertEqual(count,self.writes()); self.assertEqual(before,self.digest())
    def test_wrong_volume_serial_never_writes(self):
        with self.image.open('r+b') as disk:
            for sector in (2048,2054): disk.seek(sector*512+67); disk.write(bytes(4))
        before=self.digest(); self.assertLess(self.lib.wf_prepare(),0)
        self.assertEqual(self.error(),107); self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_full_suite_spc1_persistence_and_protected_files(self):
        self.assertEqual(self.lib.wt_suite(1),0); self.check_partition()
        for n,want in [('README.TXT',TEXT),('BIG.BIN',BIG),('SUBDIR/INNER.TXT',TEXT),('HIGH.TXT',b'HIGH\n')]:
            self.assertEqual(subprocess.check_output(['mtype','-i',f'{self.image}@@1048576','::'+n]),want)
        self.lib.wt_host_close(); self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),1),0)
        self.assertEqual(self.lib.sd_init(),0); before=self.digest(); self.assertEqual(self.lib.wt_suite(0),0)
        self.assertEqual(before,self.digest())
        self.assertEqual(self.lib.wt_suite(1),1)
        self.assertEqual(self.writes(),0); self.assertEqual(before,self.digest())
    def test_card_refusing_crc_off_uses_valid_crc(self):
        self.lib.wt_host_config(6,2)
        self.assertEqual(self.lib.wt_suite(1),0); self.check_partition()
    def test_full_suite_spc8(self):
        self.lib.wt_host_close(); self.layout=builder.prepare(self.image,spc=8)
        self.assertEqual(self.lib.wt_host_open(str(self.image).encode(),7),0); self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.lib.wt_suite(1),0); self.check_partition()

if __name__=='__main__': unittest.main(verbosity=2)
