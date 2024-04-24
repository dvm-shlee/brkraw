from __future__ import annotations
from typing import Optional
import ctypes
from ..pvobj import PvScan
from ..analyzer import ScanInfoAnalyzer, AffineAnalyzer, DataArrayAnalyzer, BaseAnalyzer


class ScanInfo(BaseAnalyzer):
    def __init__(self):
        self.warns = []
        
    @property
    def num_warns(self):
        return len(self.warns)


class ScanObj(PvScan):
    def __init__(self, pvscan: 'PvScan', reco_id: Optional[int] = None,
                 loader_address: Optional[int] = None, debug: bool=False):
        super().__init__(pvscan._scan_id, 
                         (pvscan._rootpath, pvscan._path), 
                         pvscan._contents, 
                         pvscan._recos)
        
        self.reco_id = reco_id
        self._loader_address = loader_address
        self._pvscan_address = id(pvscan)
        self.is_debug = debug
        self.set_info()
    
    def set_info(self):
        self.info = self.get_info(self.reco_id)
                
    def get_info(self, reco_id:Optional[int] = None, get_analyzer:bool = False):
        infoobj = ScanInfo()
        pvscan = self.retrieve_pvscan()
        analysed = ScanInfoAnalyzer(pvscan, reco_id, self.is_debug)
        
        if get_analyzer:
            return analysed
        for attr_name in dir(analysed):
            if 'info_' in attr_name:
                attr_vals = getattr(analysed, attr_name)
                setattr(infoobj, attr_name.replace('info_', ''), attr_vals)
                if attr_vals and attr_vals['warns']:
                    infoobj.warns.extend(attr_vals['warns'])
        return infoobj
    
    def get_affine_info(self, reco_id:Optional[int] = None):
        if reco_id:
            info = self.get_info(reco_id)
        else:
            info = self.info if hasattr(self, 'info') else self.get_info(self.reco_id)
        return AffineAnalyzer(info)
    
    def get_data_info(self, reco_id: Optional[int] = None):
        reco_id = reco_id or self.avail[0]
        recoobj = self.get_reco(reco_id)
        fileobj = recoobj.get_2dseq()
        info = self.info if hasattr(self, 'info') else self.get_info(self.reco_id)
        return DataArrayAnalyzer(info, fileobj)
    
    def get_affine(self, reco_id:Optional[int] = None, 
                   subj_type:Optional[str] = None, subj_position:Optional[str] = None):
        return self.get_affine_info(reco_id).get_affine(subj_type, subj_position)
    
    def get_dataarray(self, reco_id: Optional[int] = None):
        return self.get_data_info(reco_id).get_dataarray()
    
    def retrieve_pvscan(self):
        if self._pvscan_address:
            return ctypes.cast(self._pvscan_address, ctypes.py_object).value
    
    def retrieve_loader(self):
        if self._loader_address:
            return ctypes.cast(self._loader_address, ctypes.py_object).value
        