'''
* NOTE: Version 1.0a is rewritten from scratch to improve on the
*       shortcomings of the previous version (mainly too many false
*       positives & general instability).
*       Main change was in the identification method, which now uses
*       SimpleBlobDetector_create() ==> detector.detect(img) instead
*       of HoughCircles().
*
* USEFUL ARGUMENTS:
*   -o/--overlay: Specify overlay file
*   -a/--alpha  : Specify transperancy level (0.0 - 1.0)
*   -d/--debug  : Enable debugging
*
* VERSION: 1.1.1a
*   - ADDED   : Overlay an image/pathology
*   - MODIFIED: Significantly reduced false-positives
*   - ADDED   : Define a ROI. If blobs are detected outside
*               ROI, ignore them
*   - ADDED   : Store detected pupil color in BGR color space
*   - MODIFIED: PUT THINGS IN FUNCTIONS FOR GOD'S SAKE!
*   - ADDED   : Fallback to contour detection if BLOB fails
*   - ADDED   : Switch overlays using left click
*
* KNOWN ISSUES:
*   - Code logic is somewhat iffy and can be optimized
*   - Unable to capture pupil when looking from the side (Solution IP)
*
* AUTHOR                    :   Mohammad Odeh
* WRITTEN                   :   Aug   1st, 2016 Year of Our Lord
* LAST CONTRIBUTION DATE    :   Jul. 24th, 2018 Year of Our Lord
*
* ----------------------------------------------------------
* ----------------------------------------------------------
*
* RIGHT CLICK: Shutdown Program.
* LEFT CLICK : Switch Overlay.
'''

ver = "Live Feed Ver1.1a"
print __doc__

import  cv2                                                                     # OpenCV, the meat & potatoes
import  numpy                                                       as  np      # Image manipulation
from    timeStamp                       import  fullStamp           as  FS      # Show date/time on console output
from    imutils.video.pivideostream     import  PiVideoStream                   # Import threaded PiCam module
from    imutils.video                   import  FPS                             # Benchmark FPS
from    argparse                        import  ArgumentParser                  # Pass flags/parameters to script
from    LEDRing                         import  *                               # Let there be light
from    time                            import  sleep, time                     # Time is essential to life
import  os, platform                                                            # Directory/file manipulation

# ************************************************************************
# ===================> DEFINE VALID OPERATING SYSTEM <===================*
# ************************************************************************
if( platform.system() != "Linux" ):
    raise Exception( "{} is not supported. Please use a Linux based system.".format(platform.system()) )


# ************************************************************************
# =====================> CONSTRUCT ARGUMENT PARSER <=====================*
# ************************************************************************
ap = ArgumentParser()

ap.add_argument( "-o", "--overlay", required=False,
                 help="Path to overlay image" )

ap.add_argument( "-a", "--alpha", type=float, default=0.85,
                 help="Set alpha level.\nDefault=0.85" )

ap.add_argument( "-d", "--debug", action='store_true',
                 help="Enable debugging" )

args = vars( ap.parse_args() )

##args["debug"] = True
args["overlay"] = "/home/pi/Desktop/BETA/Alpha/Retina_w_blur_v2.png"
# ************************************************************************
# =====================> DEFINE NECESSARY FUNCTIONS <=====================
# ************************************************************************

def control( event, x, y, flags, param ):
    '''
    Left/right click mouse events
    '''
    global realDisplay, overlayImg, counter
    
    # Right button shuts down program
    if( event == cv2.EVENT_RBUTTONDOWN ):                                       # If right-click, do shutdown clean up
        try:
            colorWipe(strip, Color(0, 0, 0, 0), 0)                              # Turn OFF LED ring
            stream.stop()                                                       # Stop capturing frames from stream
            cv2.destroyAllWindows()                                             # Close any open windows
            
        except Exception as error:
            if( args["debug"] ):
                print( "{} Error caught in control()".format(FS()) )            # Specify error type
                print( "{0} {1}".format(FS(), type(error)) )                    # ...

        finally: 
            quit()                                                              # Shutdown python interpreter
     
    # Left button switches overlays
    elif( event == cv2.EVENT_LBUTTONDOWN ):                                     # If left-click, switch overlays
        print( "[INFO] Loading {}".format(overlay_name_list[counter]) ) ,       # [INFO] ...
        overlayImg = prepare_overlay( overlay_path_list[counter] )              # Switch overlay
        print( "...DONE" )                                                      # [INFO] ...
        counter += 1
        
        if( counter == len(overlay_path_list) ):
            counter = 0

# ------------------------------------------------------------------------

def placeholder( x ):
    '''
    Place holder function for trackbars. This is required
    for the trackbars to function properly.
    '''
    
    return()

# ------------------------------------------------------------------------

def setup_windows():
    '''
    Create windows and trackbars.
    '''

    global CV_win
    
    # Setup main window
    cv2.namedWindow( ver, cv2.WND_PROP_FULLSCREEN )                                                      # Start a named window for output
    cv2.setWindowProperty( ver, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN )
    cv2.setMouseCallback( ver, control )                                        # Connect mouse events to actions

    return()

# ------------------------------------------------------------------------

def setup_detector():
    '''
    Setup blob detector.

    INPUTS:-
        - NONE

    OUTPUT:-
        - parameters: BLOB detector's parameters
        - detector  : BLOB detector
    '''
    
    parameters = cv2.SimpleBlobDetector_Params()                                # Parameters
	 
    # Filter by Area.
    parameters.filterByArea = True                                              # ...
    parameters.minArea = np.pi * 15**2                                          # ...
    parameters.maxArea = np.pi * 45**2                                          # ...

    # Filter by color
    parameters.filterByColor = True                                             # ...
    parameters.blobColor = 0                                                    # ...

    # Filter by Circularity
    parameters.filterByCircularity = True                                       # ...
    parameters.minCircularity = 0.42                                            # ...
     
    # Filter by Convexity
    parameters.filterByConvexity = True                                         # ...
    parameters.minConvexity = 0.43                                              # ...
             
    # Filter by Inertia
    parameters.filterByInertia = True                                           # ...
    parameters.minInertiaRatio = 0.41                                           # ...

    # Distance Between Blobs
    parameters.minDistBetweenBlobs = 2000                                       # ...
             
    # Create a detector with the parameters
    detector = cv2.SimpleBlobDetector_create( parameters )                      # Create detector

    return( parameters, detector )
    
# ------------------------------------------------------------------------

def procFrame( image ):
    '''
    Process frame by applying a bilateral filter, a Gaussian blur,
    and an adaptive threshold + some post-processing

    INPUTS:-
        - image     : Image to be processed

    OUTPUT:-
        - processed : Processed image
    '''

    # Error handling (1/3)
    try:
        # Get trackbar position and reflect its threshold type and values
        threshType      = 1                                                     # ...
        maxValue        = 255                                                   # Update parameters
        blockSize       = 85                                                    # ...
        cte             = 50                                                    # from trackbars
        GaussianBlur    = 50                                                    # ...

        # blockSize must be an odd number
        if( blockSize%2 == 0 ):                                                 # Ensure that blockSize
            blockSize += 1                                                      # is an odd number (MUST)
        
        # Dissolve noise while maintaining edge sharpness
        processed = cv2.inRange( image, lower_bound, upper_bound )
        processed = cv2.bilateralFilter( processed, 5, 17, 17 )
        processed = cv2.GaussianBlur( processed, (5, 5), GaussianBlur )
        
        # Threshold any color that is not black to white (or vice versa)
        if( threshType == 0 ):
            processed = cv2.adaptiveThreshold( processed, maxValue,             # ...
                                               cv2.ADAPTIVE_THRESH_MEAN_C,      # Mean
                                               cv2.THRESH_BINARY, blockSize,    # Binary
                                               cte )                            # ...
        elif( threshType == 1 ):
            processed = cv2.adaptiveThreshold( processed, maxValue,             # ...
                                               cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # Gaussian
                                               cv2.THRESH_BINARY, blockSize,    # Binary
                                               cte )                            # ...
        elif( threshType == 2 ):
            processed = cv2.adaptiveThreshold( processed, maxValue,             # ...
                                               cv2.ADAPTIVE_THRESH_MEAN_C,      # Mean
                                               cv2.THRESH_BINARY_INV, blockSize,# Binary Inverted
                                               cte )                            # ...
        elif( threshType == 3 ):
            processed = cv2.adaptiveThreshold( processed, maxValue,             #
                                               cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # Gaussian
                                               cv2.THRESH_BINARY_INV, blockSize,# Binary Inverted
                                               cte )                            # ...

        # Use erosion and dilation combination to eliminate false positives.
        kernel      = cv2.getStructuringElement( cv2.MORPH_ELLIPSE, ( 3, 3 ) )  # Define kernel for filters                         
        processed   = cv2.erode ( processed, kernel, iterations=6 )             # Erode over 6 passes
        processed   = cv2.dilate( processed, kernel, iterations=3 )             # Dilate over 3 passes

        morphed     = cv2.morphologyEx( processed, cv2.MORPH_GRADIENT, kernel ) # Morph image for shits and gigs
        
    # Error handling (2/3) 
    except:
        kernel      = cv2.getStructuringElement( cv2.MORPH_ELLIPSE, ( 3, 3 ) )  # Define kernel for filters
        processed   = image                                                     # Reset image in case...
        morphed     = cv2.morphologyEx( processed, cv2.MORPH_GRADIENT, kernel ) # function done fucked up!

    # Error handling (3/3)
    finally:
        
        return( processed, morphed )                                            # Return
    
# ------------------------------------------------------------------------
initC = True
initK = True
def find_pupil( processed, overlay_frame, overlay_img, frame ):
    '''
    Find pupil by scanning for circles within an image

    INPUTS:-
        - processed     : Processed image
        - overlay_frame : The overlay empty frame
        - overlay_img   : The overlay image
        - frame         : Frame to which we should attach overlay

    OUTPUT:-
        - frame         : Image with/without overlay
                (depends whether circles were found or not)
    '''
    global ROI
    global initC, initK
    
    ROI_x_min, ROI_y_min = ROI[0]
    ROI_x_max, ROI_y_max = ROI[1]
    
    frame_failed = bool( True )                                                 # Boolean flag 1
    within_ROI   = bool( False )                                                # Boolean flag 2

    # Error handling (1/3)
    try:
        # BLOB Detector
        gray = cv2.cvtColor( frame, cv2.COLOR_BGR2GRAY )                        # Convert to grayscale
        keypoints = detector.detect( gray )                                     # Launch blob detector

        if( len(keypoints) > 0 ):                                               # If blobs are found
            if( args["debug"] ):
                if( initK ):
                    initC = True 
                    initK = False
                    print( "[INFO] cv2.SimpleBlobDetector()" )
                    
            for k in keypoints:                                                 # Iterate over found blobs
                x, y, r = int(k.pt[0]), int(k.pt[1]), int(k.size/2)             # Get co-ordinates
                pos = ( x, y, r )                                               # Pack co-ordinates
                
                if( is_inROI( pos ) ):                                          # Check if we are within ROI
                    frame = add_overlay( overlay_frame,                         # Add overlay
                                         overlay_img,                           # ...
                                         frame, pos )                           # ...
                    
                    frame_failed = bool( False )                                # Set flag to false
                    within_ROI   = bool( True  )                                # Set flag to true
                    
        else:
            # Contour Detector
            r_min   = 15                                                        # Get current r_min ...
            r_max   = 45                                                        # and r_max values
             
            _, contours, _ = cv2.findContours( processed,                       # Find contours based on their...
                                               cv2.RETR_EXTERNAL,               # external edges and keep only...
                                               cv2.CHAIN_APPROX_SIMPLE )        # intermediate points (SIMPLE)
            
            # If circles are found draw them
            if( len(contours) > 0 ):                                            # Check if we detected anything
                if( args["debug"] ):
                    if( initC ):
                        initC = False
                        initK = True                    
                        print( "[INFO] cv2.findContours()" )
                        
                for c in contours:                                              # Iterate over all contours
                    (x, y) ,r = cv2.minEnclosingCircle(c)                       # Min enclosing circle inscribing contour
                    xy = (int(x), int(y))                                       # Get circle's center...
                    r = int(r)                                                  # and radius
                    pos = ( xy[0], xy[1], r )                                   # Pack co-ordinates
                    
                    if( is_inROI( pos ) ):                                      # Check if we are within ROI
                        if( r_min <= r and r <= r_max ):                        # Check if within desired limit
                            frame = add_overlay( overlay_frame,                 # Add overlay
                                                 overlay_img,                   # ...
                                                 frame, pos )                   # ...

                            frame_failed = bool( False )                        # Set flag to false
                            within_ROI   = bool( True  )                        # Set flag to true


        if( frame_failed and not within_ROI ):
            ROI = is_inROI( update_ROI=True )                                   # Reset ROI if necessary

    # Error handling (2/3)
    except Exception as error:
        if( args["debug"] ):
            print( "{} Error caught in find_pupil()".format(FS()) )             # Specify error type
            print( "{0} {1}".format(FS(), error) )                              # ...


    # Error handling (3/3)
    finally:
        return( frame )                                                          
    
# ------------------------------------------------------------------------

def add_overlay( overlay_frame, overlay_img, frame, pos ):
    '''
    Resize and add overlay image into detected pupil location 

    INPUTS:
        - overlay_frame : The overlay empty frame
        - overlay_img   : The overlay image
        - frame         : Frame to which we should attach overlay
        - pos           : Co-ordinates where pupil is

    OUTPUT:
        - frame         : Image with overlay
    '''
    
    x, y, r = pos                                                               # Unpack co-ordinates
    
    x_min, x_max = x-r, x+r                                                     # Find min/max x-range
    y_min, y_max = y-r, y+r                                                     # Find min/max y-range

    if( x_min > 0 and y_min > 0 ):
        if( x_max < w and y_max < h ):
            
            overlay_img = cv2.resize( overlay_img, ( 2*r, 2*r ),                # Resize overlay image to fit
                                      interpolation = cv2.INTER_AREA )          # ...
            
            overlay_frame[ y_min:y_max, x_min:x_max] = overlay_img              # Place overlay image into overlay frame
            r_min       = 15                                                    # Get updated blob detector
            r_max       = 45                                                    # parameters
            alpha_val = np.interp( r, [r_min, r_max], [0.0, 1.0] )
            args["alpha"] = alpha_val
            frame = cv2.addWeighted( overlay_frame,                             # Join overlay frame (alpha)
                                     args["alpha"],                             # with actual frame (RGB)
                                     frame, 1.0, 0 )            # ...

            if( args["debug"] ):
                cv2.circle( frame, (x, y), r, (0, 255, 0), 2 )                  # Draw a circle
##                cv2.rectangle( frame, ROI[0], ROI[1], (255, 0, 0), 2 )          # Draw dynamic ROI rectangle
            
    return( frame )
        
# ------------------------------------------------------------------------

def get_avg_color( img, pos ):
    '''
    Get the average color of the ROI

    INPUTS:
        - img : image which we want the average color of

    OUTPUT:
        - NONE
    '''
    
    x, y, r = pos                                                               # Unpack co-ordinates

    img = img[ y-5:y+5, x-5:x+5 ]                                               # Crop image to the size of the pupil
    avg_color_per_row = np.average( img, axis=0 )                               # Get the average color
    avg_color = np.average( avg_color_per_row, axis=0 )                         # ...

    return( avg_color )                                                         # Return

# ------------------------------------------------------------------------

def is_inROI( xyr_points=None, update_ROI=False ):
    '''
    Determine if we are in the ROI

    INPUTS:
        - xyr_points: (x, y, r) co-ordinates

    OUTPUT:
        - inRoi     : True/False boolean
    '''
    
    global ROI, startTime

    if( update_ROI ):                                                           # If update_ROI is true
        if( time() - startTime >= timeout ):                                    #   Check for timeout
            if( args["debug"] ): print( "[INFO] ROI Reset" )                    #       [INFO] status
            startTime = time()                                                  #       Reset timer
            return( ROI_0[:] )                                                  #       Reset ROI

        else:
            return( ROI )                                                       #   Else return current ROI

    else:
        x, y, r = xyr_points                                                    # Unpack co-ordinates
        
        x_min, x_max = x-r, x+r                                                 # Find min/max x-range
        y_min, y_max = y-r, y+r                                                 # Find min/max y-range

        ROI_x_min, ROI_y_min = ROI[0]                                           # Unpack min/max
        ROI_x_max, ROI_y_max = ROI[1]                                           # ROI points

        inROI = bool( False )                                                   # Boolean flag

        if( ROI_x_min < x_min and x_max < ROI_x_max ):                          # Check if we are within ROI
            if( ROI_y_min < y_min and y_max < ROI_y_max ):                      # ...
            
                ROI[0] = ( (x_min-dx), (y_min-dy) )                             #   Update ROI
                ROI[1] = ( (x_max+dx), (y_max+dy) )                             #   ...

                inROI  = bool( True )                                           #   Set flag to True
                
                startTime = time()                                              #   Reset timer
            
            else: pass                                                          # Else we are not...
        else: pass                                                              # within ROI

        return( inROI )

# ------------------------------------------------------------------------

def prepare_overlay( img=None ):
    '''
    Load and prepare overlay images

    INPUTS:
        - img:     RAW   overlay iamge

    OUTPUT:
        - img: Processed overlay image
    '''
    
    # Check whether an overlay is specified
    if( img != None ):
        img = cv2.imread( img, cv2.IMREAD_UNCHANGED )                           # Load specific overlay
    else:
        src = "/home/pi/Desktop/BETA/Overlay.png"                               # Load default overlay
        img = cv2.imread( src  , cv2.IMREAD_UNCHANGED )                         # ...

    # Load overlay image with Alpha channel
    ( wH, wW ) = img.shape[:2]                                                  # Get dimensions
    ( B, G, R, A ) = cv2.split( img )                                           # Split into constituent channels
    B = cv2.bitwise_and( B, B, mask=A )                                         # Add the Alpha to the B channel
    G = cv2.bitwise_and( G, G, mask=A )                                         # Add the Alpha to the G channel
    R = cv2.bitwise_and( R, R, mask=A )                                         # Add the Alpha to the R channel
    img = cv2.merge( [B, G, R, A] )                                             # Finally, merge them back

    return( img )                                                               # Return processed overlay

# ************************************************************************
# ===========================> SETUP PROGRAM <===========================
# ************************************************************************

# List overlays
current_path     = os.getcwd()                                                  # Get current working directory
overlay_path     = current_path + "/Alpha"                                      # Path to overlays
overlay_path_list= []                                                           # List of images w\ full path
overlay_name_list= []                                                           # List of images' names
valid_extensions = [ ".png" ]                                                   # Allowable image extensions

for file in os.listdir( overlay_path ):                                         # Loop over images in directory
    extension    = os.path.splitext( file )[1]                                  # Get file's extensions

    if( extension.lower() not in valid_extensions ):                            # If extensions is not in valid
        continue                                                                # list, skip it.

    else:                                                                       # Else, append full file path
        overlay_path_list.append( os.path.join(overlay_path, file) )            # to list.
        overlay_name_list.append( os.path.splitext(file)[0] )                   # ...
        
# Prepare overlay
global overlayImg, counter
counter     = 0                                                                 # Overlay switcher counter
overlayImg  = prepare_overlay( args["overlay"] )                                # Prepare and process overlay

# Setup camera (x,y)
stream = PiVideoStream( resolution=(384, 288) ).start()                         # Start PiCam
sleep( 0.25 )                                                                   # Sleep for stability
realDisplay = True                                                              # Start with a normal display
colorWipe( strip, Color(255, 255, 255, 255), 0 )                                # Turn ON LED ring

# Setup main window
setup_windows()                                                                 # Create window and trackbars

# Setup BlobDetector
global detector, params
params, detector = setup_detector()                                             # Create BLOB detector + define params


######
### Setup ROI
######
global ROI, startTime
startTime = time()
timeout = 1.00
dx, dy, dROI = 35, 35, 65
ROI_0 = [ (144-dROI, 108-dROI), (144+dROI, 108+dROI) ]
ROI   = [ (144-dROI, 108-dROI), (144+dROI, 108+dROI) ]

# ************************************************************************
# =========================> MAKE IT ALL HAPPEN <=========================
# ************************************************************************
global lower_bound, upper_bound

##lower_bound = np.array( [  0,   0,  10], dtype = np.uint8 )
##upper_bound = np.array( [255, 255, 195], dtype = np.uint8 )

##lower_bound = np.array( [  0,   0,   0], dtype = np.uint8 )
##upper_bound = np.array( [ 75,  75,  75], dtype = np.uint8 )

##lower_bound = np.array( [  0,   0,  10], dtype = np.uint8 )
##upper_bound = np.array( [150, 150, 160], dtype = np.uint8 )

##lower_bound = np.array( [  0,   0,  10], dtype = np.uint8 )
##upper_bound = np.array( [200, 200, 210], dtype = np.uint8 )

lower_bound = np.array( [  0,   0,   0], dtype = np.uint8 )
upper_bound = np.array( [180, 255,  30], dtype = np.uint8 )

while( True ):
    # Capture frame
    frame = stream.read()[36:252, 48:336]                                       # Capture frame and crop it
    image = frame                                                               # Save a copy of captured frame

    # Add a 4th dimension (Alpha) to the captured frame
    (h, w) = frame.shape[:2]                                                    # Determine width and height
    frame = np.dstack([ frame, np.ones((h, w),                                  # Stack the arrays in sequence, 
                                       dtype="uint8")*255 ])                    # depth-wise ( along the z-axis )

    # Create an overlay layer
    overlay = np.zeros( ( h, w, 4 ), "uint8" )                                  # Empty np array w\ same dimensions as the frame

    # Find circles
    mask, closing = procFrame( image )                                          # Process image
##    image = find_pupil( closing, overlay, overlayImg, frame )                   # Scan for pupil
    
##    if( args["debug"] ):
##        cv2.rectangle( image, ROI_0[0], ROI_0[1], (0, 0, 255) ,2 )              # Draw initial ROI box
        
    # Display feed
    if( realDisplay ):                                                          # Show real output
        cv2.imshow( ver, image)                                                 # 
        key = cv2.waitKey(1) & 0xFF                                             # ...
    else:                                                                       # Show morphed image
        cv2.imshow( ver, closing )                                              # ...
        key = cv2.waitKey(1) & 0xFF                                             # ...
        
