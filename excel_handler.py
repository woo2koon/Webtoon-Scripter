import os
import sys
import shutil
import tempfile
import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from copy import copy
from PySide6.QtWidgets import QFileDialog, QApplication, QMessageBox

import config
from utils import restore_template

def export_to_excel(main_window):
    """
    엑셀 추출 비즈니스 로직을 처리하는 함수
    """
    if not main_window.current_episode: return
    e_path, _, _ = main_window.get_paths()
    
    try:
        main_window.save_char_data()
        main_window.save_script_data()
        c_csv = os.path.join(e_path, "character_info.csv")
        s_csv = os.path.join(e_path, "script_data.csv")
        
        char_df = pd.read_csv(c_csv, keep_default_na=False)
        script_df = pd.read_csv(s_csv, keep_default_na=False)
        
        if not os.path.exists(config.TEMPLATE_PATH): restore_template()
        wb = load_workbook(config.TEMPLATE_PATH)
        
        def copy_style(src, tgt):
            if src.has_style:
                tgt.font = copy(src.font)
                tgt.border = copy(src.border)
                tgt.fill = copy(src.fill)
                tgt.alignment = copy(src.alignment)
        
        if "캐릭터 정보" in wb.sheetnames:
            ws = wb["캐릭터 정보"]
            src_cells = [ws.cell(2, c) for c in range(1, 5)] if ws.max_row >= 2 else None
            if ws.max_row > 1: ws.delete_rows(2, ws.max_row)
            for i, row in char_df.iterrows():
                r = i + 2
                ws.cell(r, 1, row.get('Character', ''))
                ws.cell(r, 2, row.get('Age', ''))
                ws.cell(r, 3, row.get('Gender', ''))
                ws.cell(r, 4, row.get('Role', ''))
                if src_cells:
                    for c in range(1, 5): copy_style(src_cells[c-1], ws.cell(r, c))
        
        if "스크립트" in wb.sheetnames:
            ws = wb["스크립트"]
            src_cells = [ws.cell(2, c) for c in range(1, 4)] if ws.max_row >= 2 else None
            if ws.max_row > 1: ws.delete_rows(2, ws.max_row)
            dv = DataValidation(type="list", formula1="OFFSET('캐릭터 정보'!$A$2,0,0,COUNTA('캐릭터 정보'!$A:$A)-1,1)", allow_blank=True)
            ws.add_data_validation(dv)
            for i, row in script_df.iterrows():
                r = i + 2
                c1 = ws.cell(r, 1, row.get('Character', ''))
                c2 = ws.cell(r, 2, row.get('Line', ''))
                c3 = ws.cell(r, 3, "")
                dv.add(c1)
                if src_cells:
                    copy_style(src_cells[0], c1)
                    copy_style(src_cells[1], c2)
                    copy_style(src_cells[2], c3)
        
        save_path, _ = QFileDialog.getSaveFileName(main_window, "엑셀 저장", os.path.join(e_path, f"{main_window.current_title}_{main_window.current_episode}_스크립트.xlsx"), "Excel Files (*.xlsx)")
        
        if save_path:
            main_window.toast.show_message("💾 엑셀 파일 저장 및 최적화 중...", 10000)
            main_window.toast.opacity_effect.setOpacity(1.0)
            QApplication.processEvents()
            QApplication.processEvents()
            
            if sys.platform == "darwin":
                home = os.path.expanduser("~")
                temp_dir = os.path.join(home, "Library/Group Containers/UBF8T346G9.Office")
                if not os.path.exists(temp_dir):
                    try: os.makedirs(temp_dir)
                    except: temp_dir = tempfile.gettempdir()
            else:
                temp_dir = tempfile.gettempdir()

            temp_file_path = os.path.join(temp_dir, os.path.basename(save_path))
            
            wb.save(temp_file_path)
            wb.close()

            auto_save_success = False
            
            try:
                import xlwings as xw
                app = xw.App(visible=False, add_book=False)
                app.display_alerts = False
                
                if sys.platform == "win32":
                    app.interactive = False
                    app.screen_updating = False
                
                try:
                    t_wb = app.books.open(temp_file_path)
                    if sys.platform == "win32":
                        app.api.Visible = False 
                    t_wb.save()
                    t_wb.close()
                    auto_save_success = True
                except Exception as e:
                    print(f"세탁 실패: {e}")
                    auto_save_success = False
                finally:
                    app.quit()
                    if sys.platform == "win32":
                        try: app.kill()
                        except: pass
            except ImportError:
                print("xlwings 미설치")
                auto_save_success = False 

            final_nas_path = os.path.abspath(os.path.normpath(save_path))
            if os.path.exists(final_nas_path): os.remove(final_nas_path)
            shutil.move(temp_file_path, final_nas_path)
            
            if auto_save_success:
                main_window.toast.show_message("📄 엑셀파일 추출 완료", 3000)
            else:
                main_window.toast.show_message("⚠️ 추출 완료 (수동 저장 필요)", 4000)
                try:
                    if sys.platform == "win32":
                        os.startfile(final_nas_path)
                    else:
                        import subprocess
                        subprocess.call(["open", final_nas_path])
                except Exception as e:
                    print(f"파일 열기 실패: {e}")

    except Exception as e:
        QMessageBox.critical(main_window, "오류", f"저장 중 오류 발생: {e}")
