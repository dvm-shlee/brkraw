"""Docstring for public module D100, D200."""
from __future__ import annotations
from brkraw.api.data import Study
from .base import BaseMethods
from .scan import ScanToNifti
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, Literal, Union
    from pathlib import Path
    from brkraw.api import PlugInSnippet
    from nibabel.nifti1 import Nifti1Header


class StudyToNifti(Study, BaseMethods):
    """public class docstring."""
    def __init__(self, path:'Path',
                 scale_mode: Optional[Literal['header', 'apply']] = None):
        super().__init__(path)
        self.set_scale_mode(scale_mode)
        self._cache = {}
    
    def get_scan(self, scan_id: int, 
                 reco_id: Optional[int] = None):
        if scan_id not in self._cache.keys():
            pvscan = super().get_scan(scan_id).retrieve_pvobj()
            self._cache[scan_id] = ScanToNifti(pvobj=pvscan, 
                                               reco_id=reco_id, 
                                               study_address=id(self))
        return self._cache[scan_id]
    
    def get_scan_pvobj(self, scan_id: int, 
                       reco_id: Optional[int] = None):
        return super().get_scan(scan_id=scan_id, 
                                reco_id=reco_id).retrieve_pvobj()
    
    def get_scan_analyzer(self, 
                          scan_id: int, 
                          reco_id: Optional[int] = None):
        return self.get_scan(scan_id).get_scaninfo(reco_id=reco_id, 
                                                   get_analyzer=True)
    
    def get_affine(self, 
                   scan_id: int, 
                   reco_id: Optional[int] = None, 
                   subj_type: Optional[str] = None, 
                   subj_position: Optional[str] = None):
        scanobj = self.get_scan(scan_id, reco_id)
        return super().get_affine(scanobj=scanobj, 
                                  reco_id=reco_id, 
                                  subj_type=subj_type, 
                                  subj_position=subj_position)
    
    def get_dataobj(self, scan_id: int, reco_id: Optional[int] = None, 
                    scale_mode: Optional[Literal['header', 'apply']] = None):
        scale_mode = scale_mode or self.scale_mode
        scale_correction = False if not scale_mode or scale_mode == 'header' else True
        scanobj = self.get_scan(scan_id, reco_id)
        return super().get_dataobj(scanobj=scanobj, 
                                   reco_id=reco_id, 
                                   scale_correction=scale_correction)
    
    def get_data_dict(self, scan_id: int, 
                      reco_id: Optional[int] = None):
        scanobj = self.get_scan(scan_id, reco_id)
        return super().get_data_dict(scanobj=scanobj,
                                     reco_id=reco_id)

    def get_affine_dict(self, 
                        scan_id: int, 
                        reco_id: Optional[int] = None, 
                        subj_type: Optional[str] = None, 
                        subj_position: Optional[str] = None):
        scanobj = self.get_scan(scan_id=scan_id, 
                                reco_id=reco_id)
        return super().get_affine_dict(scanobj=scanobj,
                                       reco_id=reco_id,
                                       subj_type=subj_type,
                                       subj_position=subj_position)

    def update_nifti1header(self,
                            nifti1image: 'Nifti1Header',
                            scan_id: int, 
                            reco_id: Optional[int] = None, 
                            scale_mode: Optional[Literal['header', 'apply']] = None):
        scale_mode = scale_mode or self.scale_mode
        scanobj = self.get_scan(scan_id=scan_id, 
                                reco_id=reco_id)
        return super().update_nifti1header(scanobj=scanobj,
                                           nifti1image=nifti1image, 
                                           scale_mode=scale_mode)

    def get_nifti1image(self, 
                        scan_id: int, 
                        reco_id: Optional[int] = None, 
                        scale_mode: Optional[Literal['header', 'apply']] = None,
                        subj_type: Optional[str] = None, 
                        subj_position: Optional[str] = None,
                        plugin: Optional[Union['PlugInSnippet', str]] = None, 
                        plugin_kws: dict = None):
        scale_mode = scale_mode or self.scale_mode
        scanobj = self.get_scan(scan_id=scan_id,
                                reco_id=reco_id)
        return super().get_nifti1image(scanobj=scanobj,
                                       reco_id=reco_id,
                                       scale_mode=scale_mode,
                                       subj_type=subj_type, 
                                       subj_position=subj_position, 
                                       plugin=plugin, 
                                       plugin_kws=plugin_kws)
        
    @property
    def info(self):
        # scan cycle
        header = super().info['header']
        scans = super().info['scans']
        title = header['sw_version']
        date = header['date']
        print(title)
        print('-' * len(title))
        print('date: {date}')
        for key, value in header.items():
            if key not in ['date', 'sw_version']:
                print(f'{key}:\t{value}')
        print('\n[ScanID]\tMethod::Protocol')
        max_size = len(str(max(scans.keys())))
        
        for scan_id, value in scans.items():
            print(f"[{str(scan_id).zfill(max_size)}]\t{value['method']}::{value['protocol']}")
            if 'recos' in value and value['recos']:
                print('\tRECO:', list(value['recos'].keys()))