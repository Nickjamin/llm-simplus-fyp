import matlab.engine
import io

def run_simplus_headless(simplus_dir: str):
    """Executes UserMain.m headlessly and captures outputs/errors."""
    print("[MATLAB] Starting engine...")
    eng = matlab.engine.start_matlab('-nodesktop -nosplash')
    
    out = io.StringIO()
    err = io.StringIO()
    success = False
    error_msg = ""
    
    try:
        eng.cd(simplus_dir, nargout=0)
        print("[MATLAB] Executing UserMain.m...")
        eng.UserMain(nargout=0, stdout=out, stderr=err)
        success = True
    except matlab.engine.MatlabExecutionError as e:
        error_msg = str(e)
    finally:
        eng.quit()
        
    return success, out.getvalue(), err.getvalue(), error_msg