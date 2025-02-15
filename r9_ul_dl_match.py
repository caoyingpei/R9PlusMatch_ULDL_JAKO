'''
Created on 2017年9月11日

@author: T450S
'''

import os
import shutil
import struct
import time
import json
import re
import datetime
import logging  
import logging.config  
from scp_send import *  

from progressbar import  ETA, ProgressBar, SimpleProgress, AbsoluteETA
    
from ctypes import cdll
from win32netcon import PASSWORD_EXPIRED
_sopen = cdll.msvcrt._sopen
_close = cdll.msvcrt._close
_SH_DENYRW = 0x10
class R9UlDlMatch():
    '''
    R9 上下行JAKO文件匹配
    2017-10-17 增加将 文件大小小于？KB的文件转存为 空文件但名字不能改成LU
    '''

    whitelist = ['jako','txt']
    TOTAL_FRAME_NUM = 339456 # 
    C_RESULT_CONTENT = 'RESULT'
    L_DLFILE_CONTENT = 'DLFILE'
    
    def __init__(self, cfg):
        '''
        @1 读取配置文件
        '''
        print(json.dumps(cfg,indent = 4))
        logging.config.fileConfig('./configFile/log.conf')  
        self.logger = logging.getLogger('main')  
        
#         logger.info('start import module \'mod\'...')  

        self.r9_ul_file_content = cfg['R9_UL_FILE_CONTENT']
        self.r9_dl_file_exit_flag = cfg['R9_DL_FILE_EXIT']
        self.r9_exe_type = cfg["R9_EXE_TYPE"]
        
        if self.r9_dl_file_exit_flag == "TRUE":
            self.r9_dl_file_content = cfg['R9_DL_FILE_CONTENT']
        self.r9_result_file_content = cfg['R9_RESULT_FILE_CONTENT']
        self.r9_result_file_content_empty = cfg['R9_RESULT_FILE_CONTENT_EMPTY']
        self.r9_result_file_content_sms = cfg['R9_RESULT_FILE_CONTENT_SMS']
        
        self.r9_c_server_for_download_file_content = cfg['R9_C_SERVER_FOR_DOWNLOAD_FILE_CONTENT']
        '''
        @2 初始化参数
        '''
        self.r9_ul_dl_period  = cfg['R9_UL_DL_PERIOD']
        self.r9_match_how_many_min_ago  = cfg['R9_MATCH_HOW_MANY_MIN_AGO']
        self.r9_match_how_many_min_wait_for_match  = cfg['R9_MATCH_HOW_MANY_MIN_WAIT_FOR_MATCH']
        self.r9_check_period  = cfg['R9_CHECK_PERIOD']
        self.r9_check_file_status_period  = cfg['R9_CHECK_FILE_STATUS_PERIOD']
        self.r9_rm_old_file_flag = cfg['R9_RM_OLD_FILE_FLAG']
        try:
            self.r9_change_file_loc_kb_thres = cfg['R9_CHANGE_FILE_LOC_KB_THRES']
        except:
            self.r9_change_file_loc_kb_thres = 0
        self.r9_result_file_content_bak  = cfg['R9_RESULT_FILE_CONTENT_BAK']
        self.r9_result_file_content_bak_empty = cfg['R9_RESULT_FILE_CONTENT_BAK_EMPTY']
        self.r9_result_file_content_bak_sms = cfg['R9_RESULT_FILE_CONTENT_BAK_SMS']
        
        try:
            self.r9_result_remote_file_content_bak  = cfg['R9_RESULT_REMOTE_FILE_CONTENT']
            self.r9_result_remote_file_content_bak_empty = cfg['R9_RESULT_REMOTE_FILE_CONTENT_EMPTY']
            self.r9_result_remote_file_content_bak_sms = cfg['R9_RESULT_REMOTE_FILE_CONTENT_BAK_SMS']
        except:
            pass
        try:
            self.r9_r9_open_file_filter_flag = cfg['R9_OPEN_FILE_FILTER_FLAG']
            self.r9_r9_open_log_flag = cfg['R9_OPEN_LOG_FLAG']
        except:
            self.r9_r9_open_file_filter_flag = "FALSE"
            self.r9_r9_open_log_flag = "FALSE"
        self.r9_spot_beam_list = cfg['R9_SPOT_BEAM_LIST']
        self.ulfile_dict = {} 
        self.dlfile_dict = {} 
        self.total_list_len = 0
        try:
            self.r9_scp = cfg['R9_SCP']
        except:
            pass
        if 'DL'==self.r9_exe_type:
            self.r9_middle_station_name = cfg['R9_MIDDLE_STATION_NAME']
            self.r9_middle_server_file_content = cfg['R9_MIDDLE_SERVER_FILE_CONTENT']
            self._fl=scp(self.r9_scp['IP'],self.r9_scp['PORT'],self.r9_scp['USERNAME'],self.r9_scp['PASSWORD'])
            self.r9_scp_init()

    def r9_scp_init(self):
        dir_list = self._fl.scp_list_dir()
        if not self.C_RESULT_CONTENT in dir_list :
            self._fl.scp_mkdir(self.C_RESULT_CONTENT)
        if not self.L_DLFILE_CONTENT in dir_list:    
            self._fl.scp_mkdir(self.L_DLFILE_CONTENT)
    
    def r9_mk_sub_dir(self):
        dir_list = self._fl.scp_list_dir(self.C_RESULT_CONTENT)
        if not self.r9_middle_station_name in dir_list:
            self._fl.scp_mkdir(self.C_RESULT_CONTENT+'\\'+self.r9_middle_station_name)
        dir_list =self._fl.scp_list_dir(self.C_RESULT_CONTENT+'\\'+self.r9_middle_station_name)
        for spot_beam in self.r9_spot_beam_list:
            if not spot_beam in dir_list:
                self._fl.scp_mkdir(self.C_RESULT_CONTENT+'\\'+self.r9_middle_station_name+'\\'+spot_beam)
    
    def r9_scp_get_c_file_list(self):
        file_list = []
        now_time = time.time()
        print(now_time)
        sub_content = self.C_RESULT_CONTENT+'\\'+self.r9_middle_station_name
        for spot_beam in self.r9_spot_beam_list:
            spot_beam_content = sub_content+'\\'+spot_beam
            remotelist = self._fl.scp_attr(spot_beam_content)
            for file in remotelist:
                file_time = file.st_atime
                print(file_time)
                if now_time - file_time > self.r9_match_how_many_min_ago *10:
                    file_list.append(spot_beam_content+'\\'+file.filename)
        return file_list
              
    def r9_scp_download_file(self):
#         print(self.r9_c_server_file_list)
        for file in self.r9_c_server_file_list:
#                 if tmpfile[1] == 's' or tmpfile[1] == 'S':
            
            tmpfile=file.rsplit(os.sep)[-1].rsplit('.')[0]
            print(tmpfile)
            Suffix = file.rsplit(os.sep)[-1].rsplit('.')[-1]
            if not os.path.exists(self.r9_ul_file_content+'\\sms\\'):
                os.makedirs(self.r9_ul_file_content+'\\sms\\')
            if not os.path.exists(self.r9_ul_file_content+'\\lu\\'):
                os.makedirs(self.r9_ul_file_content+'\\lu\\')
            if not os.path.exists(self.r9_ul_file_content+'\\jako\\'):
                os.makedirs(self.r9_ul_file_content+'\\jako\\')
                
            if Suffix == 'txt':
                if tmpfile[1]=='s' or tmpfile[1] == 'S':
                    remotfile = self.r9_ul_file_content+'\\sms\\'+tmpfile+'.'+Suffix
                else:
                    remotfile = self.r9_ul_file_content+'\\lu\\'+tmpfile+'.'+Suffix
                
            elif Suffix == 'jako':
                remotfile = self.r9_ul_file_content+'\\jako\\'+tmpfile+'.'+Suffix
            else:
                print('[FILE]->%D FORMAT ERROR',file)
                #self.logger.error('[FILE]->%D FORMAT ERROR',file)    
            
#             print()
            if tmpfile[26:29] in self.r9_spot_beam_list:
                try:
                    self._fl.scp_get(file, remotfile)
                    if -1==remotfile.find("jako"):
                        shutil.copy(remotfile,self.r9_middle_server_file_content)
                    self._fl.scp_rm_file(file)
                except:
                    print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
#                     #self.logger.error('[FILE]->%D  COULD NOT BE FOUND',remotfile)
            else:
                try:
                    self._fl.scp_rm_file(file)
                except:
                    pass
#                 pass
            self.proc_count_len = self.proc_count_len+1
#             print(self.proc_count_len)
            self.r9_match_progress_bar_print(self.proc_count_len)    
    def r9_scp_upload_file(self):
        for key in self.dlfile_dict.keys():
            for i in range(len(self.dlfile_dict[key])):
                current_file_loc = self.dlfile_dict[key][i]
                tmpfile=self.dlfile_dict[key][i].rsplit(os.sep)[-1].rsplit('.')[0]
                if tmpfile[1] == 's' or tmpfile[1] == 'S':
                    remotfile = self.L_DLFILE_CONTENT+'\\'+tmpfile+'.txt'
                    remotfile_bak = self.r9_result_file_content_bak+'\\'+tmpfile+'.txt'
                else:
                    remotfile = self.L_DLFILE_CONTENT+'\\'+tmpfile+'.jako'
                    remotfile_bak = self.r9_result_file_content_bak+'\\'+tmpfile+'.jako'
                try:
                    shutil.copy(current_file_loc,remotfile_bak)
                    self._fl.scp_put(remotfile,current_file_loc)
                    os.remove(current_file_loc)
                except:
                    print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
#                     #self.logger.error('[FILE]->%D  COULD NOT BE FOUND',remotfile)
#                 print(remotfile)
#                 self._fl.scp_put(remotfile,current_file_loc)
                
                
                self.proc_count_len = self.proc_count_len+1
                
                self.r9_match_progress_bar_print(self.proc_count_len)        
            
    def is_open(self,file_name):
        if not self.r9_r9_open_file_filter_flag=='TRUE':
            return False
        try:
            firstSize = os.path.getsize(file_name)
            time.sleep(0.01)
            secondSize = os.path.getsize(file_name)
            if firstSize == secondSize:
                return False
            else:
                return False
        except:
            return True
    def r9_get_ul_file(self):
        file_list = list()
        for parent,dirnames,filenames in os.walk(self.r9_ul_file_content):
            for filename in filenames:
                ext = filename.split('.')[-1]
                if ext in self.whitelist:
                    if self.is_open(os.path.join(parent,filename))==False  and self.r9_file_filter(os.path.join(parent,filename)) == True:
                        file_list.append(os.path.join(parent,filename))
        return file_list
    def r9_get_c_server_file(self):
        file_list = list()
        for parent,dirnames,filenames in os.walk(self.r9_c_server_for_download_file_content):
            for filename in filenames:
                ext = filename.split('.')[-1]
                if ext in self.whitelist:
                    if self.is_open(os.path.join(parent,filename))==False and self.r9_just_time_filter(os.path.join(parent,filename)) == True:
                        file_list.append(os.path.join(parent,filename))
        return file_list

    def r9_get_dl_file(self):
        file_list = list()
        for parent,dirnames,filenames in os.walk(self.r9_dl_file_content):
            for filename in filenames:
                ext = filename.split('.')[-1]
                if ext in self.whitelist:
                    if self.is_open(os.path.join(parent,filename))==False and self.r9_file_filter(os.path.join(parent,filename)) == True:
                        file_list.append(os.path.join(parent,filename))
        return file_list
    def r9_ullist_proc(self):
        cnt = 0
        for file in self.r9_ulfile_list:
            cut_file=file.rsplit('.',1)[0]
            tmpList = cut_file.split('#')
#             print(tmpList)
            #key = str(int(tmpList[len(tmpList)-2])%128)+tmpList[len(tmpList)-3]
            key = tmpList[len(tmpList)-1][0:16]
            fn = int(tmpList[len(tmpList)-1][16:22])
            cut_file = cut_file+'.'+file.rsplit('.',1)[-1]
            #G新增加部分 ， 大于等于339456的为大站文件 ，小于339456的为小站文件 
            if fn < self.TOTAL_FRAME_NUM :
                if key in  self.ulfile_dict.keys():
                    self.ulfile_dict[key].append(cut_file)
                else:
                    self.ulfile_dict[key] =[cut_file] 
            else:
                cnt=cnt+1
                if key in  self.dlfile_dict.keys():
                    self.dlfile_dict[key].append(cut_file)
                else:
                    self.dlfile_dict[key] =[cut_file] 
        return cnt
    def r9_progress_bar_init(self,maxValue):
        self._pre_index_=0
        self._max_value_=maxValue
        widgets = ['progress: ',SimpleProgress(),' | ' , ' | ', ETA(), ' | ', AbsoluteETA()]
        self.pbar = ProgressBar(widgets=widgets, maxval=maxValue).start()
        
    def r9_progress_bar_update(self,index):
        self.pbar.update(index)
        
    def r9_progress_bar_finish(self):
        self.pbar.finish()
        
    def r9_match_progress_bar_print(self,index):
        if (index - self._pre_index_)*100/self._max_value_ >1:
            self._pre_index_=index
            self.r9_progress_bar_update(index)   
        
    def r9_split(self,file):
        cut_file=file.rsplit('.',1)[0]
        return cut_file.split('#')
    
    def r9_dllist_proc(self):
        for file in self.r9_dlfile_list:
            cut_file=file.rsplit('.',1)[0]
            tmpList = cut_file.split('#')
            #key = str(int(tmpList[len(tmpList)-2])%128)+tmpList[len(tmpList)-3]
            #cut_file = cut_file+'.'+file.rsplit('.',1)[-1]
            key = tmpList[len(tmpList)-1][0:16]
            #fn = int(tmpList[len(tmpList)-1][16:22])
            cut_file = cut_file+'.'+file.rsplit('.',1)[-1]
            if key in  self.dlfile_dict.keys():
                self.dlfile_dict[key].append(cut_file)
            else:
                self.dlfile_dict[key] =[cut_file] 
                
    def r9_get_voice_file_total_framenum(self,file,uLdLtype):
        total_framenum = 0
        fp = open(file,'rb')
        try:
            fp.read(32)
            while True:
                read_result = struct.unpack('B',fp.read(1))[0]
                # 第二个比特 为0 
                if read_result%2==0 and uLdLtype == 'UL':
                    total_framenum = total_framenum+1
                elif read_result%2==1 and uLdLtype == 'DL':
                    total_framenum = total_framenum+1
                if read_result%4>1:
                    fp.read(30)
#                 if type == 'UL':
#                     total_framenum = total_framenum+1
        except:
            fp.close()
        return  total_framenum
    def r9_copy_to_middle_station(self,file,spot_beam_id):
#         print(self.r9_c_server_for_download_file_content)
        for dir in os.listdir(self.r9_c_server_for_download_file_content):
#             print(dir)
            if os.path.isdir(self.r9_c_server_for_download_file_content+'\\'+dir):
                for sub_dir in os.listdir(self.r9_c_server_for_download_file_content+'\\'+dir):
#                     print(sub_dir)
                    if sub_dir == spot_beam_id:
                        shutil.copy(file,self.r9_c_server_for_download_file_content+'\\'+dir+'\\'+sub_dir)
    def r9_rm_middle_station_time_out_dir(self):
#         print(self.r9_c_server_for_download_file_content)
        for dir in os.listdir(self.r9_c_server_for_download_file_content):
#             print(dir)
#             filenames = os.walk(self.r9_c_server_for_download_file_content+'\\'+dir)[2]
            totalFileCount = sum([len(files) for root, dirs, files in os.walk(self.r9_c_server_for_download_file_content+'\\'+dir)])
            print('CNT = %d | %s'%(totalFileCount,self.r9_c_server_for_download_file_content+'\\'+dir))
            if totalFileCount>300:
                shutil.rmtree(self.r9_c_server_for_download_file_content+'\\'+dir)
#             if os.path.isdir(self.r9_c_server_for_download_file_content+'\\'+dir):
#                 for sub_dir in os.listdir(self.r9_c_server_for_download_file_content+'\\'+dir):
# #                     print(sub_dir)
#                     if sub_dir == spot_beam_id:
#                         shutil.copy(file,self.r9_c_server_for_download_file_content+'\\'+dir+'\\'+sub_dir)
                     
        
        
        
    def r9_voice_merge(self,ulfile_Loc,dlfile_Loc,remoteefile_Loc,UlFrameNum,DlFrameNum):
        
        '''
        @语音格式
                        前32个字节是文件头部，没有具体意义。暂定：前4字节为字符串"jako"，后28字节填0
                        从第33个字节开始，是文件具体内容。第33个字节bit0表示上下行，0表示上行，1表示下行，bit1表示是否静音，0表示静音，1表示有声音。如果为静音，表示40ms的静音，无后续字节，如果有声音，之后连续26个byte表示40ms编码码流。
                        文件无结束标志。
                        如示例文件"示例.jako"表示40ms的下行静音和40ms的上行语音
        @设计策略
           @1 统计上行的帧号 与下行的相差范围，计算上下行头的位置，
           @2 统计上下行的总帧数，与头的位置一起统计尾巴的位置
        '''
        '''
            @data: 2017-11-20
            @function:跨越最大帧的情况 
            @author: cyp
        '''
        if abs(UlFrameNum - DlFrameNum+self.TOTAL_FRAME_NUM)<=self.r9_ul_dl_period :
            UlFrameNum=self.TOTAL_FRAME_NUM+UlFrameNum
            
        if abs(DlFrameNum - UlFrameNum +self.TOTAL_FRAME_NUM)<=self.r9_ul_dl_period :
            DlFrameNum=self.TOTAL_FRAME_NUM+DlFrameNum
            
        
        cnt = UlFrameNum - DlFrameNum
        cnt = (cnt-2*(cnt//26))//4-2
        cnt = cnt//2
        print('UlFrameNum %d',UlFrameNum)
        print('DlFrameNum %d',DlFrameNum)
        if cnt > 0 :
            dlhead = 0 
            ulhead = cnt
        else:
            dlhead = -cnt 
            ulhead = 0    
        
        ultail =  ulhead+self.r9_get_voice_file_total_framenum(ulfile_Loc,'UL')
        dltail  = dlhead+self.r9_get_voice_file_total_framenum(dlfile_Loc,'DL')
        
        print(dlhead,'-',dltail)
        print(ultail,'-',ulhead)
        
        totol_frame_num = 0
        if dltail> ultail:
            totol_frame_num = dltail
        else:
            totol_frame_num = ultail
            
        
        fw = open(remoteefile_Loc,'wb')
        fu = open(ulfile_Loc,'rb')
        fd = open(dlfile_Loc,'rb')
        try:
            fd.read(32)
            fw.write(fu.read(32))
            for i in range(totol_frame_num):
                if i < dlhead or i>dltail-1:
                    fw.write(b'\x01')
                else:
                    while True:
                        read_byte = fd.read(1)
                        read_result = struct.unpack('B',read_byte)[0]
                        if read_result%2==1:
                        # 第二个比特 为0 
                            fw.write(read_byte)
                            if read_result%4>1:
                                fw.write(fd.read(30))
                            break
                        else:
                            if read_result%4>1:
                                fd.read(30)
                           
        
                if i < ulhead or i>ultail-1:
                    fw.write(b'\x00')
                else:
                    while True:
                        read_byte = fu.read(1)
                        read_result = struct.unpack('B',read_byte)[0]
                        if read_result%2==0:
                        # 第二个比特 为0 
                            fw.write(read_byte)
                            if read_result%4>1:
                                fw.write(fu.read(30))
                            break
                        else:
                            if read_result%4>1:
                                fu.read(30)       
        except:
            #self.logger.error('FORMAT_ERROR %s %s'%(ulfile_Loc,dlfile_Loc))  
            print('[ERROR :] FORMAT_ERROR %s %s'%(ulfile_Loc,dlfile_Loc))
        fw.close()
        fd.close()
        fu.close()
    def r9_ul_dl_file_match_proc(self,key):
        
        i=0
        if key == '0000000000000000':
            return
        while i< len(self.ulfile_dict[key]):
            j=0
            match_flag = 0
            while j < len(self.dlfile_dict[key]):
                ulfile= self.ulfile_dict[key][i]
                dlfile= self.dlfile_dict[key][j]
                ulfile = ulfile.rsplit('.')[0]
                dlfile = dlfile.rsplit('.')[0]
                ultmpList = self.r9_split(ulfile)
                dltmpList = self.r9_split(dlfile)
                UlFrameNum= int(ultmpList[-1][16:22])%self.TOTAL_FRAME_NUM
                DlFrameNum= int(dltmpList[-1][16:22])%self.TOTAL_FRAME_NUM
                print('UlFrameNum %d',UlFrameNum)
                print('DlFrameNum %d',DlFrameNum)
                if abs(UlFrameNum - DlFrameNum)>self.r9_ul_dl_period and abs(DlFrameNum - UlFrameNum +self.TOTAL_FRAME_NUM)>self.r9_ul_dl_period :
                    pass
                else:
                    tmpfile=ulfile.rsplit(os.sep)[-1]
                    tmpfile1=dlfile.rsplit(os.sep)[-1]
                    tmpfile = tmpfile.replace(tmpfile[0:33],tmpfile[0:29]+'FFFF')
                    tmpfile = tmpfile.replace(tmpfile[0:3],tmpfile1[0:3])
                    tmpfile = tmpfile.replace(ultmpList[-2],dltmpList[-2])
                    if tmpfile[1] == 's' or tmpfile[1] == 'S':
                        j=j+1
                        continue
                    if tmpfile[0] == 'n' or tmpfile[0] == 'N':
                        remotfile = self.r9_result_file_content_empty+'\\'+tmpfile[0:len(tmpfile)-23]+'.txt'
                    else:
                        remotfile = self.r9_result_file_content+'\\'+tmpfile[0:len(tmpfile)-23]+'.jako'
                    
                    if tmpfile[2] == 'I' or tmpfile[2] == 'i':
                        r=re.compile('#.*?#.*?#N#(.*?)#N#')
                        dl_telnum = r.findall(dlfile)
                    
                    split_header=remotfile.rsplit('\\',1)
                    
    
                    
                    if tmpfile[0] == 'n' or tmpfile[0] == 'N':
                        path = split_header[0]
                        bak_path = self.r9_result_file_content_bak_empty + '\\'+self.r9_get_year_month_day()
                    else:
                        path = split_header[0]
                        bak_path = self.r9_result_file_content_bak + '\\'+self.r9_get_year_month_day()    
                    replace_header= split_header[1].replace(split_header[1][0:29],split_header[1][0:26]\
                                    +dlfile.rsplit('\\',1)[1][26:29])

                    if 'i'==replace_header[2] or 'I'==replace_header[2]:
                        try:
                            replace_header = replace_header.replace('#N#N#','#N#'+dl_telnum[0]+'#')
                        except:
                            pass
                    
                    if not os.path.exists(path):
                        os.makedirs(path) 
                    if not os.path.exists(bak_path):
                        os.makedirs(bak_path) 
                    remotfile = path+'\\'+replace_header
                    remotfile_bak = bak_path+'\\'+replace_header 
    
                    spot_beam_id = tmpfile[26:29]                      
                    if self.r9_r9_open_log_flag == 'TRUE':
                        if os.path.exists(remotfile):
                            print('[WARNING] : {%s} is exsit'%remotfile)
                            pass
                        print('[MATCHED] :\n    ->%s \n    ->%s'%(ulfile+'.jako',dlfile+'.jako'))
                    try:
                        self.r9_voice_merge(ulfile+'.jako',dlfile+'.jako',remotfile,UlFrameNum,DlFrameNum)
    
                        self.r9_copy_to_middle_station(remotfile, spot_beam_id)
                    except:
                        print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
                        j=j+1
                        continue
                        #self.logger.error('[FILE]->%D  COULD NOT BE FOUND',remotfile) 
                    if self.r9_rm_old_file_flag == 'TRUE':
                        try:
                            if tmpfile[0] == 'n' or tmpfile[0] == 'N':
                                os.remove(ulfile+'.txt')
                                os.remove(dlfile+'.txt')
                            else:
                                os.remove(ulfile+'.jako')
                                os.remove(dlfile+'.jako')
                        except:
                            pass
                    match_flag =1 
                    break
                j=j+1
            if match_flag == 1:
                self.proc_count_len = self.proc_count_len+2
                self.r9_match_progress_bar_print(self.proc_count_len)
                self.ulfile_dict[key].remove(self.ulfile_dict[key][i])
                self.dlfile_dict[key].remove(self.dlfile_dict[key][j])
            else:
                i=i+1
                
         
    def r9_ul_dl_match(self):
        '''
        @匹配规则:
        @1 上下行 SB_MASK相同
        @2 上下行的随机值相同
        @3 上下行的帧号不超过R9_ULDL_PERIOD 
        '''
        for key in self.dlfile_dict.keys(): 
            if key in self.ulfile_dict.keys():
                self.r9_ul_dl_file_match_proc(key)
        self.r9_ul_file_save()
        self.r9_dl_file_save()
        self.ulfile_dict= {}
        self.dlfile_dict= {}
    def r9_just_time_filter(self,filfile):
        file_time = os.path.getctime(filfile)
        now_time = time.time()
        if not now_time - file_time > self.r9_match_how_many_min_ago *10:
            return False 
        else:
            return True    
    def r9_match_time_filter(self,filfile):
        file_time = os.path.getctime(filfile)
        now_time = time.time()
        if not now_time - file_time > self.r9_match_how_many_min_wait_for_match *60:
            return False 
        else:
            return True        
    def r9_file_filter(self,filfile):
        '''
        @过滤策略 
                         
        @1     获取文件的时间 如果时间 与当前时间相差超过2s则认为可以通过过滤
        
        @2     文件所包含的‘#’数目过滤
        '''

        file_time = os.path.getctime(filfile)
        now_time = time.time()
        if not now_time - file_time > self.r9_match_how_many_min_ago *10:
            return False  
        if  not filfile.count('#') == 7:
            #self.logger.error('[ERROR :] FILE_NAME FORMAT ERROR [%s]'%filfile)
            print('[ERROR :] FILE_NAME FORMAT ERROR [%s]'%filfile)
            return False
        return True
         
    def r9_dl_file_save(self):
        '''
        @1 处理匹配的程序
        '''
        for key in self.dlfile_dict.keys():
            for i in range(len(self.dlfile_dict[key])):
                current_file_loc = self.dlfile_dict[key][i]
                if False == self.r9_match_time_filter(current_file_loc):
                    self.proc_count_len = self.proc_count_len+1
                    self.r9_match_progress_bar_print(self.proc_count_len)  
                    continue
                tmpfile=self.dlfile_dict[key][i].rsplit(os.sep)[-1].rsplit('.')[0]
                tmpfile = tmpfile.replace(tmpfile[0:33],tmpfile[0:29]+'0001')
                if tmpfile[1] == 's' or tmpfile[1] == 'S':
                        path = self.r9_result_file_content_sms 
                        if not os.path.exists(path):
                            os.makedirs(path) 
                        bak_path = self.r9_result_file_content_bak_sms + '\\' + self.r9_get_year_month_day()
                        if not os.path.exists(bak_path):
                            os.makedirs(bak_path)
                        remotfile = tmpfile[0:len(tmpfile)-23]+'.txt'
                elif tmpfile[0] == 'N' or tmpfile[0] == 'n':
                    path = self.r9_result_file_content_empty 
                    if not os.path.exists(path):
                        os.makedirs(path) 
                    bak_path = self.r9_result_file_content_bak_empty + '\\' + self.r9_get_year_month_day()
                    if not os.path.exists(bak_path):
                        os.makedirs(bak_path)
                        
                    remotfile = 'n'+tmpfile[1:len(tmpfile)-23]+'.txt'
                    
                else:
                    path = self.r9_result_file_content 
                    if not os.path.exists(path):
                        os.makedirs(path) 
                    bak_path = self.r9_result_file_content_bak + '\\' + self.r9_get_year_month_day()
                    if not os.path.exists(bak_path):
                        os.makedirs(bak_path)
                    remotfile = tmpfile[0:len(tmpfile)-23]+'.jako'
                remotfile_bak = bak_path+'\\'+remotfile
                remotfile = path+'\\'+remotfile
                if self.r9_r9_open_log_flag == 'TRUE':
                    print(current_file_loc)
                    print('->',remotfile)
                self.proc_count_len = self.proc_count_len+1
                self.r9_match_progress_bar_print(self.proc_count_len)
                spot_beam_id =  tmpfile[26:29]                     
                if self.r9_rm_old_file_flag == 'TRUE' :
                    if tmpfile[1] == 's' or tmpfile[1] == 'S':
                        try:
                            shutil.move(current_file_loc,remotfile)
                            self.r9_copy_to_middle_station(remotfile, spot_beam_id)
                        except:
                            print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
                    elif tmpfile[0] == 'N' or tmpfile[0] == 'n':
                        try:
                            f=open(remotfile,'w')
                            f.close()
                            self.r9_copy_to_middle_station(remotfile, spot_beam_id)
                            os.remove(current_file_loc)
                        except:
                            print("[ERROR] DL FILE SAVE ERROR!")
                    else:
                        try:
                            shutil.move(current_file_loc,remotfile)
                            self.r9_copy_to_middle_station(remotfile, spot_beam_id)
                        except:
                            print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
                    
                else:
                    try:
                        shutil.copy(current_file_loc,remotfile)
                        shutil.copy(remotfile,self.r9_c_server_for_download_file_content)
                    except:
                        print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
    def r9_get_year_month_day(self):
        
        return '%04d%02d%02d'%(datetime.datetime.now().year,
                datetime.datetime.now().month,
                datetime.datetime.now().day)
    def r9_ul_file_save(self):
        '''
        @1 处理匹配的程序
        @2 11.19 添加短信处理文件夹
        '''
        for key in self.ulfile_dict.keys():
            for i in range(len(self.ulfile_dict[key])):
                current_file_loc = self.ulfile_dict[key][i]
                if False == self.r9_match_time_filter(current_file_loc):
                    self.proc_count_len = self.proc_count_len+1
                    self.r9_match_progress_bar_print(self.proc_count_len)  
                    continue
                tmpfile=self.ulfile_dict[key][i].rsplit('.')[0].rsplit(os.sep)[-1]
                
                
                
                tep = tmpfile.split('#')
                if tmpfile[1] == 's' or tmpfile[1] == 'S':
                    remotfile = self.r9_result_file_content_sms+'\\'+tmpfile[0:len(tmpfile)-23]+'.txt'
                elif tmpfile[0] == 'n' or tmpfile[0] == 'N':
                    remotfile = self.r9_result_file_content_empty+'\\'+tmpfile[0:len(tmpfile)-23]+'.txt'
                else:
                    remotfile = self.r9_result_file_content+'\\'+tmpfile[0:len(tmpfile)-23]+'.jako'
                
                
                split_header=remotfile.rsplit('\\',1)
                replace_header = split_header[1]
                path = split_header[0]
                    
                if tmpfile[1] == 's' or tmpfile[1] == 'S':
                    bak_path = self.r9_result_file_content_bak_sms + '\\'+self.r9_get_year_month_day()
                elif tmpfile[0] == 'n' or tmpfile[0] == 'N':
                    bak_path = self.r9_result_file_content_bak_empty + '\\'+self.r9_get_year_month_day()
                else:
                    bak_path = self.r9_result_file_content_bak + '\\'+self.r9_get_year_month_day()
                
                if not os.path.exists(path):
                    os.makedirs(path) 
                if not os.path.exists(bak_path):
                    os.makedirs(bak_path) 
                remotfile = path+'\\'+replace_header
                remotfile_bak = bak_path+'\\'+replace_header
                if self.r9_r9_open_log_flag == 'TRUE':
                    print(current_file_loc)
                    print('->',remotfile)
                self.proc_count_len = self.proc_count_len+1
                self.r9_match_progress_bar_print(self.proc_count_len)  
                spot_beam_id =  tmpfile[26:29]       
                if self.r9_rm_old_file_flag == 'TRUE':
                    if tmpfile[1] == 's' or tmpfile[1] == 'S':
                        try:
                            shutil.move(current_file_loc,remotfile)
                            self.r9_copy_to_middle_station(remotfile,spot_beam_id)
                        except:
                            print('[FILE]->%D  COULD NOT BE FOUND',remotfile)    
                    elif tmpfile[0] == 'n' or tmpfile[0] == 'N':
                        try:
                            f=open(remotfile,'w')
                            f.close()
                            f=open(remotfile_bak,'w')
                            f.close()

                            self.r9_copy_to_middle_station(remotfile,spot_beam_id)
                            os.remove(current_file_loc)
                        except:
                            print('[ERROR] UL FILE SAVE ERROR',remotfile)   
                    else:
                        try:
                            shutil.move(current_file_loc,remotfile)
                            self.r9_copy_to_middle_station(remotfile,spot_beam_id)
                        except:
                            print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
                else:
                    try:
                        shutil.copy(current_file_loc,remotfile)
                        shutil.copy(remotfile,self.r9_c_server_for_download_file_content)
                    except:
                        print('[FILE]->%D  COULD NOT BE FOUND',remotfile)

    def dl_upload_file_proc(self):
        '''
            @1下行处理程序 ，
                @1 配置文件中result content为上传下行文件的目录，dlfile 为下行源文件程序，ulfile为上行传下来的原文件程序，cserver 为上行源目录 其他目录无需考虑
            @2           
        '''
        for key in self.dlfile_dict.keys():
            for i in range(len(self.dlfile_dict[key])):
                current_file_loc = self.dlfile_dict[key][i]
                tmpfile=self.dlfile_dict[key][i].rsplit(os.sep)[-1].rsplit('.')[0]
                if tmpfile[1] == 's' or tmpfile[1] == 'S':
                    remotfile = self.r9_result_file_content+'\\'+tmpfile+'.txt'
                    remotfile_bak = self.r9_result_file_content_bak+'\\'+tmpfile+'.txt'
                else:
                    remotfile = self.r9_result_file_content+'\\'+tmpfile+'.jako'
                    remotfile_bak = self.r9_result_file_content_bak+'\\'+tmpfile+'.jako'
                try:
                    shutil.copy(current_file_loc,remotfile_bak)
                    shutil.move(current_file_loc,remotfile)
                except:
                    print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
#                     #self.logger.error('[FILE]->%D  COULD NOT BE FOUND',remotfile)
                self.proc_count_len = self.proc_count_len+1
                
                self.r9_match_progress_bar_print(self.proc_count_len)
    def dl_download_file_proc(self):
        for file in self.r9_c_server_file_list:
#                 if tmpfile[1] == 's' or tmpfile[1] == 'S':
            tmpfile=file.rsplit(os.sep)[-1].rsplit('.')[0]
            Suffix = file.rsplit(os.sep)[-1].rsplit('.')[-1]
            if not os.path.exists(self.r9_ul_file_content+'\\sms\\'):
                os.makedirs(self.r9_ul_file_content+'\\sms\\')
            if not os.path.exists(self.r9_ul_file_content+'\\lu\\'):
                os.makedirs(self.r9_ul_file_content+'\\lu\\')
            if not os.path.exists(self.r9_ul_file_content+'\\jako\\'):
                os.makedirs(self.r9_ul_file_content+'\\jako\\')
            if Suffix == 'txt':
                if tmpfile[1]=='s' or tmpfile[1] == 'S':
                    remotfile = self.r9_ul_file_content+'\\sms\\'+tmpfile+'.'+Suffix
                else:
                    remotfile = self.r9_ul_file_content+'\\lu\\'+tmpfile+'.'+Suffix
                
            elif Suffix == 'jako':
                remotfile = self.r9_ul_file_content+'\\jako\\'+tmpfile+'.'+Suffix
            else:
                print('[FILE]->%D FORMAT ERROR',file)
                #self.logger.error('[FILE]->%D FORMAT ERROR',file)    
            print(tmpfile)
            if tmpfile[26:29] in self.r9_spot_beam_list:
                try:
                    shutil.move(file,remotfile)
                except:
                    print('[FILE]->%D  COULD NOT BE FOUND',remotfile)
#                     #self.logger.error('[FILE]->%D  COULD NOT BE FOUND',remotfile)
            else:
                os.remove(file) 
            self.proc_count_len = self.proc_count_len+1
            print(self.proc_count_len)
            self.r9_match_progress_bar_print(self.proc_count_len)
    def r9_copy_file_to_remote_content(self):
        path = self.r9_result_file_content
        bak_remote = self.r9_result_remote_file_content_bak
        bak_path = self.r9_result_file_content_bak + '\\'+self.r9_get_year_month_day()
        if not os.path.exists(bak_remote):
            os.makedirs(bak_remote) 
        if not os.path.exists(bak_path):
            os.makedirs(bak_path) 
        for parent,dirnames,filenames in os.walk(path):
            for filename in filenames:
                try:
                    shutil.copy(os.path.join(parent,filename), os.path.join(bak_remote,filename) )
                    shutil.move(os.path.join(parent,filename),os.path.join(bak_path,filename) )
                except:
                    pass 
        
        
        path_sms = self.r9_result_file_content_sms 
        bak_remote_sms = self.r9_result_remote_file_content_bak_sms
        bak_path_sms = self.r9_result_file_content_bak_sms + '\\'+self.r9_get_year_month_day()
        if not os.path.exists(bak_remote_sms):
            os.makedirs(bak_remote_sms) 
        if not os.path.exists(bak_path_sms):
            os.makedirs(bak_path_sms) 
        for parent,dirnames,filenames in os.walk(path_sms):
            for filename in filenames:
                try:
                    shutil.copy(os.path.join(parent,filename), os.path.join(bak_remote_sms,filename) )
                    shutil.move(os.path.join(parent,filename), os.path.join(bak_path_sms,filename) )
                except:
                    pass
        
        
        path_empty = self.r9_result_file_content_empty
        bak_remote_empty = self.r9_result_remote_file_content_bak_empty
        bak_path_empty = self.r9_result_file_content_bak_empty + '\\'+self.r9_get_year_month_day()
        if not os.path.exists(bak_remote_empty):
            os.makedirs(bak_remote_empty)
        if not os.path.exists(bak_path_empty):
            os.makedirs(bak_path_empty) 
        for parent,dirnames,filenames in os.walk(path_empty):
            for filename in filenames:
                try:
                    shutil.copy(os.path.join(parent,filename), os.path.join(bak_remote_empty,filename))
                    shutil.move(os.path.join(parent,filename), os.path.join(bak_path_empty,filename))
                except:
                    pass 
        
        #            self.r9_result_remote_file_content_bak  = cfg['R9_RESULT_REMOTE_FILE_CONTENT']
        #    self.r9_result_remote_file_content_bak_empty = cfg['R9_RESULT_REMOTE_FILE_CONTENT_EMPTY']
        #    self.r9_result_remote_file_content_bak_sms = cfg['R9_RESULT_REMOTE_FILE_CONTENT_BAK_SMS']
        
        

        
    
    def run(self):
        while True:
            print('%s [INFO] : start match ul dl file'%(time.ctime()))

            '''
            @todo: 程序测试
            @todo: 上下行文件的过滤（暂时不考虑）
            '''
            try:
                if 'UL'==self.r9_exe_type:
                    self.r9_rm_middle_station_time_out_dir()
                    
                    self.r9_ulfile_list=self.r9_get_ul_file()
                
                    self.r9_ullist_proc()
                    if self.r9_dl_file_exit_flag == "TRUE":
                        self.r9_dlfile_list = self.r9_get_dl_file()
                        
                        self.total_list_len = len(self.r9_ulfile_list)+len(self.r9_dlfile_list)
                        
                        
                        self.proc_count_len = 0
                        self.r9_progress_bar_init(self.total_list_len)
                        
                        self.r9_dllist_proc()
                        
                        self.r9_ul_dl_match()
                        self.r9_copy_file_to_remote_content()
                        
                        self.r9_progress_bar_finish()
                    else:
                        self.r9_ul_file_save()
                        self.ulfile_dict= {}
                elif 'DL'==self.r9_exe_type:
                    self.r9_scp_init()
                    self.r9_mk_sub_dir()
                    self.dlfile_dict= {}
                     
                    self.r9_c_server_file_list=[]
                    self.r9_c_server_file_list=self.r9_scp_get_c_file_list()
                    
                    self.r9_dlfile_list=self.r9_get_dl_file()
                    self.r9_dllist_proc()
                    self.total_list_len = len(self.r9_c_server_file_list)+len(self.r9_dlfile_list)
                    print('C station file count = ',len(self.r9_c_server_file_list))
                    print('L station file count = ',len(self.r9_dlfile_list))
                    self.proc_count_len = 0
                    self.r9_progress_bar_init(self.total_list_len)
                     
                    self.r9_scp_upload_file()
                    self.r9_scp_download_file()
                     
                    self.r9_progress_bar_finish()    
                else:
                    print("UNKOWN EXE TYPE")
                    sys.exit(0)         
            except:
                self.logger.exception('Exception Logged')
                sys.exit(0)            
            time.sleep(self.r9_check_period)
