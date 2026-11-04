import matlab.engine
import io
import concurrent.futures
import time
import platform
import subprocess

def force_kill_matlab(eng=None):
    """Forcefully kills hanging MATLAB processes at the OS level and disarms Python GC."""
    print("\n[MATLAB] Force killing engine at OS level...")
    
    # Disarm the Python object so __del__ doesn't crash when it gets garbage collected
    if eng is not None:
        try:
            eng.exit = lambda: None
        except Exception:
            pass
            
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "MATLAB.exe"], capture_output=True)
        else:
            subprocess.run(["pkill", "-9", "-f", "MATLAB"], capture_output=True)
    except Exception as e:
        print(f"[MATLAB] Failed to force kill: {e}")

def start_matlab_engine(retries=3):
    """Starts a persistent MATLAB engine instance for batch execution with retries."""
    print("[MATLAB] Starting persistent engine...")
    for attempt in range(retries):
        try:
            eng = matlab.engine.start_matlab('-nodesktop -nosplash -noFigureWindows')
            if eng is not None:
                return eng
        except Exception as e:
            print(f"[MATLAB] Engine start failed (attempt {attempt+1}/{retries}): {e}")
            time.sleep(2)
    print("[MATLAB] CRITICAL: Failed to initialize engine.")
    return None

def ensure_healthy_engine(eng):
    """Pings the engine workspace. If dead or contaminated, kills and restarts it."""
    if eng is not None:
        try:
            eng.eval("1;", nargout=0)
            return eng
        except Exception:
            pass
    
    force_kill_matlab(eng)
    return start_matlab_engine()

def run_simplus_headless(eng, simplus_dir: str, timeout_sec: int = 60):
    """Executes UserMain.m using a pre-existing MATLAB engine instance."""
    out = io.StringIO()
    err = io.StringIO()
    success = False
    error_msg = ""
    
    eng = ensure_healthy_engine(eng)
    if eng is None:
        return False, "", "", "MATLAB engine is dead and could not be restarted.", None

    try:
        eng.cd(simplus_dir, nargout=0)
        eng.eval("clear all; close all;", nargout=0)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(eng.UserMain, nargout=0, stdout=out, stderr=err)
            try:
                future.result(timeout=timeout_sec)
                success = True
            except concurrent.futures.TimeoutError:
                error_msg = f"MATLAB execution timed out after {timeout_sec}s."
                out.write(f"\n[ERROR] {error_msg}")
                
                # Pass the engine reference to be disarmed before the kill
                force_kill_matlab(eng)
                eng = start_matlab_engine()
                
    except matlab.engine.MatlabExecutionError as e:
        error_msg = str(e)
    except Exception as e:
        error_msg = str(e)
        
    return success, out.getvalue(), err.getvalue(), error_msg, eng