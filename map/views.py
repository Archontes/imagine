import os
from django.http import HttpResponse, StreamingHttpResponse

from decals import settings

import matplotlib
matplotlib.use('Agg')

# We add a version number to each layer, to allow long cache times
# for the tile JPEGs.  Increment this version to invalidate
# client-side caches.

tileversions = {
    'sfd': [1,],
    'halpha': [1,],

    'decals-dr2': [1],

    'decals-dr1k': [1],
    'decals-model-dr1k': [1],
    'decals-resid-dr1k': [1],

    'decals-dr1n': [1],
    'decals-model-dr1n': [1],
    'decals-resid-dr1n': [1],

    'decals-dr1j': [1],
    'decals-model-dr1j': [1],
    'decals-resid-dr1j': [1],
    'decals-nexp-dr1j': [1],

    'decals-wl': [4],

    'decam-depth-g': [1],
    'decam-depth-r': [1],
    'decam-depth-z': [1],

    'unwise-w1w2': [1],
    'unwise-w3w4': [1],
    'unwise-w1234': [1],

    'cutouts': [1],
    }

catversions = {
    'decals-dr1j': [1,],
    'decals-dr2': [1,],
    'ngc': [1,],
    }

oneyear = (3600 * 24 * 365)

class MercWCSWrapper(object):
    def __init__(self, wcs, wrap):
        self.wcs = wcs
        self.wrap = float(wrap)
    def radec2pixelxy(self, ra, dec):
        X = self.wcs.radec2pixelxy(ra, dec)
        (ok,x,y) = X
        x += (x < -self.wrap/2) * self.wrap
        x -= (x >  self.wrap/2) * self.wrap
        return (ok,x,y)
    def __getattr__(self, name):
        return getattr(self.wcs, name)
    def __setattr__(self, name, val):
        if name in ['wcs', 'wrap']:
            self.__dict__[name] = val
            return
        return setattr(self.wcs, name, val)

def trymakedirs(fn):
    dirnm = os.path.dirname(fn)
    if not os.path.exists(dirnm):
        try:
            os.makedirs(dirnm)
        except:
            pass

def _read_tan_wcs(sourcefn, ext, hdr=None, W=None, H=None):
    from astrometry.util.util import Tan
    wcs = None
    if not sourcefn.endswith('.gz'):
        try:
            wcs = Tan(sourcefn, ext)
        except:
            pass
    if wcs is None:
        import fitsio
        # maybe gzipped; try fitsio header.
        if hdr is None:
            hdr = fitsio.read_header(sourcefn, ext)
        if W is None or H is None:
            F = fitsio.FITS(sourcefn)
            info = F[ext].get_info()
            H,W = info['dims']
        wcs = Tan(*[float(x) for x in [
                    hdr['CRVAL1'], hdr['CRVAL2'], hdr['CRPIX1'], hdr['CRPIX2'],
                    hdr['CD1_1'], hdr['CD1_2'], hdr['CD2_1'], hdr['CD2_2'],
                    W, H]])
    return wcs

def ra2long(ra):
    lng = 180. - ra
    lng += 360 * (lng < 0.)
    lng -= 360 * (lng > 360.)
    return lng

def send_file(fn, content_type, unlink=False, modsince=None, expires=3600,
              filename=None):
    import datetime
    '''
    modsince: If-Modified-Since header string from the client.
    '''
    st = os.stat(fn)
    f = open(fn)
    if unlink:
        os.unlink(fn)
    # file was last modified...
    lastmod = datetime.datetime.fromtimestamp(st.st_mtime)

    if modsince:
        #print 'If-modified-since:', modsince #Sat, 22 Nov 2014 01:12:39 GMT
        ifmod = datetime.datetime.strptime(modsince, '%a, %d %b %Y %H:%M:%S %Z')
        #print 'Parsed:', ifmod
        #print 'Last mod:', lastmod
        dt = (lastmod - ifmod).total_seconds()
        if dt < 1:
            from django.http import HttpResponseNotModified
            return HttpResponseNotModified()

    res = StreamingHttpResponse(f, content_type=content_type)
    # res['Cache-Control'] = 'public, max-age=31536000'
    res['Content-Length'] = st.st_size
    if filename is not None:
        res['Content-Disposition'] = 'attachment; filename="%s"' % filename
    # expires in an hour?
    now = datetime.datetime.utcnow()
    then = now + datetime.timedelta(0, expires, 0)
    timefmt = '%a, %d %b %Y %H:%M:%S GMT'
    res['Expires'] = then.strftime(timefmt)
    res['Last-Modified'] = lastmod.strftime(timefmt)
    return res

def index(req):
    layer = req.GET.get('layer', 'decals-dr1j')
    # Nice spiral galaxy
    ra, dec, zoom = 244.7, 7.4, 13
    # EDR2 region
    #ra, dec, zoom = 243.7, 8.2, 13
    # Top of DR1
    #ra,dec,zoom = 113.49, 29.86, 13

    try:
        zoom = int(req.GET.get('zoom', zoom))
    except:
        pass
    try:
        ra = float(req.GET.get('ra',ra))
    except:
        pass
    try:
        dec = float(req.GET.get('dec', dec))
    except:
        pass

    lat,lng = dec, ra2long(ra)

    url = req.build_absolute_uri(settings.ROOT_URL) + '/{id}/{ver}/{z}/{x}/{y}.jpg'
    caturl = settings.CAT_URL

    smallcaturl = settings.ROOT_URL + '/{id}/{ver}/cat.json?ralo={ralo}&rahi={rahi}&declo={declo}&dechi={dechi}'

    tileurl = settings.TILE_URL

    subdomains = settings.SUBDOMAINS
    # convert to javascript
    subdomains = '[' + ','.join(["'%s'" % s for s in subdomains]) + '];'

    static_tile_url = settings.STATIC_TILE_URL

    bricksurl = settings.ROOT_URL + '/bricks/?north={north}&east={east}&south={south}&west={west}&id={id}'
    ccdsurl = settings.ROOT_URL + '/ccds/?north={north}&east={east}&south={south}&west={west}&id={id}'

    baseurl = req.path + '?'

    from django.shortcuts import render

    return render(req, 'index.html',
                  dict(ra=ra, dec=dec, lat=lat, long=lng, zoom=zoom,
                       layer=layer, tileurl=tileurl,
                       baseurl=baseurl, caturl=caturl, bricksurl=bricksurl,
                       smallcaturl=smallcaturl,
                       ccdsurl=ccdsurl,
                       static_tile_url=static_tile_url,
                       subdomains=subdomains,
                       showSources='sources' in req.GET,
                       showNgc='ngc' in req.GET,
                       showBricks='bricks' in req.GET,
                       showCcds='ccds' in req.GET,
                       showVcc='vcc' in req.GET,
                       showSpec='spec' in req.GET,
                       maxNativeZoom = settings.MAX_NATIVE_ZOOM,
                       enable_nexp = settings.ENABLE_NEXP,
                       enable_vcc = settings.ENABLE_VCC,
                       enable_wl = settings.ENABLE_WL,
                       ))

def get_tile_wcs(zoom, x, y):
    from astrometry.util.util import anwcs_create_mercator_2

    zoom = int(zoom)
    zoomscale = 2.**zoom
    x = int(x)
    y = int(y)
    if zoom < 0 or x < 0 or y < 0 or x >= zoomscale or y >= zoomscale:
        raise RuntimeError('Invalid zoom,x,y %i,%i,%i' % (zoom,x,y))

    # tile size
    zoomscale = 2.**zoom
    W,H = 256,256
    if zoom == 0:
        rx = ry = 0.5
    else:
        rx = zoomscale/2 - x
        ry = zoomscale/2 - y
    rx = rx * W
    ry = ry * H
    wcs = anwcs_create_mercator_2(180., 0., rx, ry,
                                  zoomscale, W, H, 1)
    if wcs is not None:
        wcs = MercWCSWrapper(wcs, 2**zoom * W)

    return wcs, W, H, zoomscale, zoom,x,y

def get_scaled(scalepat, scalekwargs, scale, basefn):
    from scipy.ndimage.filters import gaussian_filter
    import fitsio
    from astrometry.util.util import Tan
    import tempfile
    import numpy as np

    if scale <= 0:
        return basefn
    fn = scalepat % dict(scale=scale, **scalekwargs)
    if not os.path.exists(fn):

        # print 'Does not exist:', fn
        sourcefn = get_scaled(scalepat, scalekwargs, scale-1, basefn)
        # print 'Source:', sourcefn
        if sourcefn is None or not os.path.exists(sourcefn):
            # print 'Image source file', sourcefn, 'not found'
            return None
        try:
            I,hdr = fitsio.read(sourcefn, header=True)
        except:
            print 'Failed to read:', sourcefn
            return None
        #print 'source image:', I.shape
        H,W = I.shape
        # make even size; smooth down
        if H % 2 == 1:
            I = I[:-1,:]
        if W % 2 == 1:
            I = I[:,:-1]
        im = gaussian_filter(I, 1.)
        #print 'im', im.shape
        # bin
        I2 = (im[::2,::2] + im[1::2,::2] + im[1::2,1::2] + im[::2,1::2])/4.
        I2 = I2.astype(np.float32)
        #print 'I2:', I2.shape
        # shrink WCS too
        wcs = _read_tan_wcs(sourcefn, 0, hdr=hdr, W=W, H=H)
        # include the even size clip; this may be a no-op
        H,W = im.shape
        wcs = wcs.get_subimage(0, 0, W, H)
        subwcs = wcs.scale(0.5)
        hdr = fitsio.FITSHDR()
        subwcs.add_to_header(hdr)
        trymakedirs(fn)
        dirnm = os.path.dirname(fn)
        f,tmpfn = tempfile.mkstemp(suffix='.fits.tmp', dir=dirnm)
        os.close(f)
        # To avoid overwriting the (empty) temp file (and fitsio
        # printing "Removing existing file")
        os.unlink(tmpfn)
        fitsio.write(tmpfn, I2, header=hdr, clobber=True)
        os.rename(tmpfn, fn)
        print 'Wrote', fn
    return fn

# "PR"
#rgbkwargs=dict(mnmx=(-0.3,100.), arcsinh=1.))

rgbkwargs = dict(mnmx=(-1,100.), arcsinh=1.)

rgbkwargs_nexp = dict(mnmx=(0,25), arcsinh=1.,
                      scales=dict(g=(2,1),r=(1,1),z=(0,1)))

def jpeg_cutout_decals_dr1j(req):
    return cutout_decals(req, jpeg=True)

def fits_cutout_decals_dr1j(req):
    return cutout_decals(req, fits=True)

def cutout_decals(req, jpeg=False, fits=False):
    ra  = float(req.GET['ra'])
    dec = float(req.GET['dec'])
    pixscale = float(req.GET.get('pixscale', 0.262))
    maxsize = 512
    size   = min(int(req.GET.get('size',    256)), maxsize)
    width  = min(int(req.GET.get('width',  size)), maxsize)
    height = min(int(req.GET.get('height', size)), maxsize)

    kwa = {}

    tag = req.GET.get('tag', None)
    print 'Requested tag:', tag
    if not tag in ['decals-dr1n', 'decals-model', 'decals-resid']:
        # default
        tag = 'decals-dr1j'
    print 'Using tag:', tag

    imagetag = 'image'
    if tag == 'decals-model':
        tag = 'decals-dr1j'
        imagetag = 'model'
        kwa.update(add_gz=True)
    elif tag == 'decals-resid':
        tag = 'decals-dr1j'
        imagetag = 'resid'
        kwa.update(model_gz=True)

    bricks = None
    if tag == 'decals-dr1n':
        bricks = get_dr1n_bricks()
        

    bands = req.GET.get('bands', 'grz')
    bands = [b for b in 'grz' if b in bands]

    from astrometry.util.util import Tan
    import numpy as np
    import fitsio
    import tempfile

    ps = pixscale / 3600.
    raps = -ps
    decps = ps
    if jpeg:
        decps *= -1.
    wcs = Tan(*[float(x) for x in [ra, dec, (width+1)/2., (height+1)/2.,
                                   raps, 0., 0., decps, width, height]])

    zoom = 14 - int(np.round(np.log2(pixscale / 0.262)))
    zoom = max(0, min(zoom, 16))

    ver = 1

    rtn = map_coadd_bands(req, ver, zoom, 0, 0, bands, 'cutouts',
                          tag,
                          wcs=wcs, bricks=bricks,
                          imagetag=imagetag, rgbkwargs=rgbkwargs,
                          savecache=False, get_images=fits, **kwa)
    #filename='cutout_%.4f_%.4f.jpg' % (ra,dec))
    if jpeg:
        return rtn
    ims = rtn

    hdr = fitsio.FITSHDR()
    hdr['SURVEY'] = 'DECaLS'
    hdr['VERSION'] = 'DR1'
    hdr['BANDS'] = ''.join(bands)
    for i,b in enumerate(bands):
        hdr['BAND%i' % i] = b
    wcs.add_to_header(hdr)

    f,tmpfn = tempfile.mkstemp(suffix='.fits')
    os.close(f)
    os.unlink(tmpfn)

    if len(bands) > 1:
        cube = np.empty((len(bands), height, width), np.float32)
        for i,im in enumerate(ims):
            cube[i,:,:] = im
    else:
        cube = ims[0]
    del ims
    fitsio.write(tmpfn, cube, clobber=True,
                 header=hdr)
    
    return send_file(tmpfn, 'image/fits', unlink=True, filename='cutout_%.4f_%.4f.fits' % (ra,dec))


Tdepth = None
Tdepthkd = None

def map_decam_depth(req, ver, zoom, x, y, savecache=False, band=None,
                    ignoreCached=False):
    global Tdepth
    global Tdepthkd

    if band is None:
        band = req.GET.get('band')
    if not band in ['g','r','z']:
        raise RuntimeError('Invalid band')
    tag = 'decam-depth-%s' % band
    zoom = int(zoom)
    zoomscale = 2.**zoom
    x = int(x)
    y = int(y)
    if zoom < 0 or x < 0 or y < 0 or x >= zoomscale or y >= zoomscale:
        raise RuntimeError('Invalid zoom,x,y %i,%i,%i' % (zoom,x,y))
    ver = int(ver)
    if not ver in tileversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    basedir = settings.DATA_DIR
    tilefn = os.path.join(basedir, 'tiles', tag,
                          '%i/%i/%i/%i.jpg' % (ver, zoom, x, y))
    if os.path.exists(tilefn) and not ignoreCached:
        print 'Cached:', tilefn
        return send_file(tilefn, 'image/jpeg', expires=oneyear,
                         modsince=req.META.get('HTTP_IF_MODIFIED_SINCE'))
    from astrometry.util.util import Tan
    from astrometry.libkd.spherematch import match_radec
    from astrometry.libkd.spherematch import tree_build_radec, tree_search_radec
    from astrometry.util.fits import fits_table
    from astrometry.util.starutil_numpy import degrees_between
    import numpy as np
    import fitsio
    try:
        wcs, W, H, zoomscale, zoom,x,y = get_tile_wcs(zoom, x, y)
    except RuntimeError as e:
        return HttpResponse(e.strerror)
    rlo,d = wcs.pixelxy2radec(W, H/2)[-2:]
    rhi,d = wcs.pixelxy2radec(1, H/2)[-2:]
    r,d1 = wcs.pixelxy2radec(W/2, 1)[-2:]
    r,d2 = wcs.pixelxy2radec(W/2, H)[-2:]

    r,d = wcs.pixelxy2radec(W/2, H/2)[-2:]
    rad = max(degrees_between(r, d, rlo, d1),
              degrees_between(r, d, rhi, d2))

    if Tdepth is None:
        T = fits_table(os.path.join(basedir, 'decals-zpt-nondecals.fits'),
                            columns=['ccdra','ccddec','arawgain', 'avsky',
                                     'ccdzpt', 'filter', 'crpix1','crpix2',
                                     'crval1','crval2','cd1_1','cd1_2',
                                     'cd2_1','cd2_2', 'naxis1', 'naxis2', 'exptime', 'fwhm'])
        T.rename('ccdra',  'ra')
        T.rename('ccddec', 'dec')

        Tdepth = {}
        Tdepthkd = {}
        for b in ['g','r','z']:
            Tdepth[b] = T[T.filter == b]
            Tdepthkd[b] = tree_build_radec(Tdepth[b].ra, Tdepth[b].dec)

    T = Tdepth[band]
    Tkd = Tdepthkd[band]

    #I,J,d = match_radec(T.ra, T.dec, r, d, rad + 0.2)
    I = tree_search_radec(Tkd, r, d, rad + 0.2)
    print len(I), 'CCDs in range'
    if len(I) == 0:
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(settings.STATIC_URL + 'blank.jpg')

    depthiv = np.zeros((H,W), np.float32)
    for t in T[I]:
        twcs = Tan(*[float(x) for x in [
            t.crval1, t.crval2, t.crpix1, t.crpix2,
            t.cd1_1, t.cd1_2, t.cd2_1, t.cd2_2, t.naxis1, t.naxis2]])
        w,h = t.naxis1, t.naxis2
        r,d = twcs.pixelxy2radec([1,1,w,w], [1,h,h,1])
        ok,x,y = wcs.radec2pixelxy(r, d)
        #print 'x,y coords of CCD:', x, y
        x0 = int(x.min())
        x1 = int(x.max())
        y0 = int(y.min())
        y1 = int(y.max())
        if y1 < 0 or x1 < 0 or x0 >= W or y0 >= H:
            continue

        readnoise = 10. # e-; 7.0 to 15.0 according to DECam Data Handbook
        skysig = np.sqrt(t.avsky * t.arawgain + readnoise**2) / t.arawgain
        zpscale = 10.**((t.ccdzpt - 22.5)/2.5) * t.exptime
        sig1 = skysig / zpscale
        psf_sigma = t.fwhm / 2.35
        # point-source depth
        psfnorm = 1./(2. * np.sqrt(np.pi) * psf_sigma)
        detsig1 = sig1 / psfnorm

        #print '5-sigma point-source depth:', NanoMaggies.nanomaggiesToMag(detsig1 * 5.)

        div = 1 / detsig1**2
        depthiv[max(y0,0):min(y1,H), max(x0,0):min(x1,W)] += div

    ptsrc = -2.5 * (np.log10(np.sqrt(1./depthiv) * 5) - 9)
    ptsrc[depthiv == 0] = 0.

    if savecache:
        trymakedirs(tilefn)
    else:
        import tempfile
        f,tilefn = tempfile.mkstemp(suffix='.jpg')
        os.close(f)

    import pylab as plt
    plt.imsave(tilefn, ptsrc, vmin=22., vmax=25., cmap='hot')#nipy_spectral')

    return send_file(tilefn, 'image/jpeg', unlink=(not savecache))


def map_decals_wl(req, ver, zoom, x, y):
    tag = 'decals-wl'
    ignoreCached = False
    filename = None
    forcecache = False

    from decals import settings
    savecache = settings.SAVE_CACHE

    zoom = int(zoom)
    zoomscale = 2.**zoom
    x = int(x)
    y = int(y)
    if zoom < 0 or x < 0 or y < 0 or x >= zoomscale or y >= zoomscale:
        raise RuntimeError('Invalid zoom,x,y %i,%i,%i' % (zoom,x,y))
    ver = int(ver)
    if not ver in tileversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    basedir = settings.DATA_DIR
    tilefn = os.path.join(basedir, 'tiles', tag,
                          '%i/%i/%i/%i.jpg' % (ver, zoom, x, y))
    if os.path.exists(tilefn) and not ignoreCached:
        print 'Cached:', tilefn
        return send_file(tilefn, 'image/jpeg', expires=oneyear,
                         modsince=req.META.get('HTTP_IF_MODIFIED_SINCE'),
                         filename=filename)
    else:
        print 'Tile image does not exist:', tilefn
    from astrometry.util.resample import resample_with_wcs, OverlapError
    from astrometry.util.util import Tan
    from astrometry.libkd.spherematch import match_radec
    from astrometry.util.fits import fits_table
    from astrometry.util.starutil_numpy import degrees_between
    from legacypipe.common import get_rgb
    import numpy as np
    import fitsio

    try:
        wcs, W, H, zoomscale, zoom,x,y = get_tile_wcs(zoom, x, y)
    except RuntimeError as e:
        return HttpResponse(e.strerror)

    mydir = os.path.join(basedir, 'coadd', 'weak-lensing')

    rlo,d = wcs.pixelxy2radec(W, H/2)[-2:]
    rhi,d = wcs.pixelxy2radec(1, H/2)[-2:]
    r,d1 = wcs.pixelxy2radec(W/2, 1)[-2:]
    r,d2 = wcs.pixelxy2radec(W/2, H)[-2:]
    #dlo = min(d1, d2)
    #dhi = max(d1, d2)

    r,d = wcs.pixelxy2radec(W/2, H/2)[-2:]
    rad = degrees_between(r, d, rlo, d1)

    fn = os.path.join(mydir, 'index.fits')
    if not os.path.exists(fn):
        #
        ii,rr,dd = [],[],[]
        for i in range(1, 52852+1):
            imgfn = os.path.join(mydir, 'map%i.fits' % i)
            print imgfn
            hdr = fitsio.read_header(imgfn)
            r = hdr['CRVAL1']
            d = hdr['CRVAL2']
            ii.append(i)
            rr.append(r)
            dd.append(d)
        T = fits_table()
        T.ra  = np.array(rr)
        T.dec = np.array(dd)
        T.i   = np.array(ii)
        T.writeto(fn)

    T = fits_table(fn)
    I,J,d = match_radec(T.ra, T.dec, r, d, rad + 0.2)
    T.cut(I)
    print len(T), 'weak-lensing maps in range'
    
    if len(I) == 0:
        from django.http import HttpResponseRedirect
        if forcecache:
            # create symlink to blank.jpg!
            trymakedirs(tilefn)
            src = os.path.join(settings.STATIC_ROOT, 'blank.jpg')
            if os.path.exists(tilefn):
                os.unlink(tilefn)
            os.symlink(src, tilefn)
            print 'Symlinked', tilefn, '->', src
        return HttpResponseRedirect(settings.STATIC_URL + 'blank.jpg')

    r,d = wcs.pixelxy2radec([1,1,1,W/2,W,W,W,W/2],
                            [1,H/2,H,H,H,H/2,1,1])[-2:]

    foundany = False
    rimg = np.zeros((H,W), np.float32)
    rn   = np.zeros((H,W), np.uint8)
    for tilei in T.i:
        fn = os.path.join(mydir, 'map%i.fits' % tilei)
        try:
            bwcs = _read_tan_wcs(fn, 0)
        except:
            print 'Failed to read WCS:', fn
            savecache = False
            import traceback
            import sys
            traceback.print_exc(None, sys.stdout)
            continue

        foundany = True
        print 'Reading', fn
        ok,xx,yy = bwcs.radec2pixelxy(r, d)
        xx = xx.astype(np.int)
        yy = yy.astype(np.int)
        imW,imH = int(bwcs.get_width()), int(bwcs.get_height())
        M = 10
        xlo = np.clip(xx.min() - M, 0, imW)
        xhi = np.clip(xx.max() + M, 0, imW)
        ylo = np.clip(yy.min() - M, 0, imH)
        yhi = np.clip(yy.max() + M, 0, imH)
        if xlo >= xhi or ylo >= yhi:
            continue

        subwcs = bwcs.get_subimage(xlo, ylo, xhi-xlo, yhi-ylo)
        slc = slice(ylo,yhi), slice(xlo,xhi)
        try:
            f = fitsio.FITS(fn)[0]
            img = f[slc]
            del f
        except:
            print 'Failed to read image and WCS:', fn
            savecache = False
            import traceback
            import sys
            traceback.print_exc(None, sys.stdout)
            continue

        try:
            Yo,Xo,Yi,Xi,nil = resample_with_wcs(wcs, subwcs, [], 3)
        except OverlapError:
            print 'Resampling exception'
            continue

        rimg[Yo,Xo] += img[Yi,Xi]
        rn  [Yo,Xo] += 1
    rimg /= np.maximum(rn, 1)

    if forcecache:
        savecache = True

    if savecache:
        trymakedirs(tilefn)
    else:
        import tempfile
        f,tilefn = tempfile.mkstemp(suffix='.jpg')
        os.close(f)

    import pylab as plt

    # S/N
    #lo,hi = 1.5, 5.0
    lo,hi = 0, 5.0
    rgb = plt.cm.hot((rimg - lo) / (hi - lo))
    plt.imsave(tilefn, rgb)
    print 'Wrote', tilefn

    return send_file(tilefn, 'image/jpeg', unlink=(not savecache),
                     filename=filename)




B_dr2 = None

def map_decals_dr2(req, ver, zoom, x, y, savecache=None,
                    model=False, resid=False, nexp=False,
                    **kwargs):
    if savecache is None:
        savecache = settings.SAVE_CACHE
    global B_dr2
    if B_dr2 is None:
        from astrometry.util.fits import fits_table
        import numpy as np
        B_dr2 = fits_table(os.path.join(settings.DATA_DIR, 'decals-dr2',
                                         'decals-bricks.fits'))

    imagetag = 'image'
    tag = 'decals-dr2'
    imagedir = 'decals-dr2'
    rgb = rgbkwargs
    return map_coadd_bands(req, ver, zoom, x, y, 'grz', tag, imagedir,
                           imagetag=imagetag,
                           rgbkwargs=rgb,
                           bricks=B_dr2,
                           savecache=savecache, **kwargs)


B_dr1n = None

def get_dr1n_bricks():
    global B_dr1n
    if B_dr1n is not None:
        return B_dr1n
    from astrometry.util.fits import fits_table
    import numpy as np
    B_dr1n = fits_table(os.path.join(settings.DATA_DIR,
                                     'decals-bricks.fits'))
    print 'Total bricks:', len(B_dr1n)
    B_dr1n.cut(np.logical_or(
        # Virgo
        (B_dr1n.ra > 185.) * (B_dr1n.ra < 190.) *
        (B_dr1n.dec > 10.)  * (B_dr1n.dec < 15.),
        # Arjun's LSB
        (B_dr1n.ra > 147.2) * (B_dr1n.ra < 147.8) *
        (B_dr1n.dec > -0.4)  * (B_dr1n.dec < 0.4)
    ))
    print len(B_dr1n), 'bricks in Virgo/LSB region'
    return B_dr1n


def map_decals_model_dr1n(*args, **kwargs):
    return map_decals_dr1n(*args, model=True, model_gz=False, **kwargs)

def map_decals_resid_dr1n(*args, **kwargs):
    return map_decals_dr1n(*args, resid=True, model_gz=False, **kwargs)

def map_decals_dr1n(req, ver, zoom, x, y, savecache=None,
                    model=False, resid=False, nexp=False,
                    **kwargs):
    if savecache is None:
        savecache = settings.SAVE_CACHE
    B_dr1n = get_dr1n_bricks()

    imagetag = 'image'
    tag = 'decals-dr1n'
    imagedir = 'decals-dr1n'
    rgb = rgbkwargs
    if model:
        imagetag = 'model'
        tag = 'decals-model-dr1n'
        scaledir = 'decals-dr1n'
        kwargs.update(model_gz=False, add_gz=True, scaledir=scaledir)
    if resid:
        imagetag = 'resid'
        kwargs.update(modeldir = 'decals-dr1n-model')
        tag = 'decals-resid-dr1n'
    # if nexp:
    #     imagetag = 'nexp'
    #     tag = 'decals-nexp-dr1n'
    #     rgb = rgbkwargs_nexp

    return map_coadd_bands(req, ver, zoom, x, y, 'grz', tag, imagedir,
                           imagetag=imagetag,
                           rgbkwargs=rgb,
                           bricks=B_dr1n,
                           savecache=savecache, **kwargs)


B_dr1k = None

def map_decals_model_dr1k(*args, **kwargs):
    return map_decals_dr1k(*args, model=True, model_gz=False, **kwargs)

def map_decals_dr1k(req, ver, zoom, x, y, savecache=None,
                    model=False, resid=False, nexp=False,
                    **kwargs):
    if savecache is None:
        savecache = settings.SAVE_CACHE
    global B_dr1k
    if B_dr1k is None:
        from astrometry.util.fits import fits_table
        import numpy as np

        B_dr1k = fits_table(os.path.join(settings.DATA_DIR, 'decals-dr1k',
                                         'decals-bricks-exist.fits'))
        B_dr1k.cut((B_dr1k.ra > 148.7) * (B_dr1k.ra < 151.5) *
                   (B_dr1k.dec > 0.9)  * (B_dr1k.dec < 3.6))
        # B_dr1k.cut(reduce(np.logical_or, [B_dr1k.has_image_g,
        #                                   B_dr1k.has_image_r,
        #                                   B_dr1k.has_image_z]))
        # B_dr1k.has_g = B_dr1k.has_image_g
        # B_dr1k.has_r = B_dr1k.has_image_r
        # B_dr1k.has_z = B_dr1k.has_image_z
        print len(B_dr1k), 'bricks in COSMOS region'
        print sum(B_dr1k.has_g), 'with g'
        print sum(B_dr1k.has_r), 'with r'
        print sum(B_dr1k.has_z), 'with z'
        B_dr1k.cut(reduce(np.logical_or, [B_dr1k.has_g > 0,
                                          B_dr1k.has_r > 0,
                                          B_dr1k.has_z > 0]))
        print len(B_dr1k), 'bricks with coverage'

    imagetag = 'image'
    tag = 'decals-dr1k'
    imagedir = 'decals-dr1k'
    rgb = rgbkwargs
    if model:
        imagetag = 'model'
        tag = 'decals-model-dr1k'
        scaledir = 'decals-dr1k'
        kwargs.update(model_gz=False, add_gz=True, scaledir=scaledir)
    if resid:
        imagetag = 'resid'
        kwargs.update(modeldir = 'decals-dr1k-model')
        tag = 'decals-resid-dr1k'
    if nexp:
        imagetag = 'nexp'
        tag = 'decals-nexp-dr1k'
        rgb = rgbkwargs_nexp

    return map_coadd_bands(req, ver, zoom, x, y, 'grz', tag, imagedir,
                           imagetag=imagetag,
                           rgbkwargs=rgb,
                           bricks=B_dr1k,
                           savecache=savecache, **kwargs)




B_dr1j = None

def map_decals_dr1j(req, ver, zoom, x, y, savecache=None,
                    model=False, resid=False, nexp=False,
                    **kwargs):
    if savecache is None:
        savecache = settings.SAVE_CACHE
    global B_dr1j
    if B_dr1j is None:
        from astrometry.util.fits import fits_table
        import numpy as np

        B_dr1j = fits_table(os.path.join(settings.DATA_DIR, 'decals-dr1',
                                         'decals-bricks-exist.fits'))
        B_dr1j.cut(reduce(np.logical_or, [B_dr1j.has_image_g,
                                          B_dr1j.has_image_r,
                                          B_dr1j.has_image_z]))
        B_dr1j.has_g = B_dr1j.has_image_g
        B_dr1j.has_r = B_dr1j.has_image_r
        B_dr1j.has_z = B_dr1j.has_image_z
        print len(B_dr1j), 'bricks with images'

    imagetag = 'image'
    tag = 'decals-dr1j'
    imagedir = 'decals-dr1j'
    rgb = rgbkwargs
    if model:
        imagetag = 'model'
        tag = 'decals-model-dr1j'
        #imagedir = 'decals-dr1j-model'
        scaledir = 'decals-dr1j'
        kwargs.update(model_gz=False, add_gz=True, scaledir=scaledir)
        #kwargs.update(model_gz=True, scaledir=scaledir)
    if resid:
        imagetag = 'resid'
        kwargs.update(modeldir = 'decals-dr1j-model',
                      model_gz=True)
        tag = 'decals-resid-dr1j'
    if nexp:
        imagetag = 'nexp'
        tag = 'decals-nexp-dr1j'
        rgb = rgbkwargs_nexp

    return map_coadd_bands(req, ver, zoom, x, y, 'grz', tag, imagedir,
                           imagetag=imagetag,
                           rgbkwargs=rgb,
                           bricks=B_dr1j,
                           savecache=savecache, **kwargs)

def map_decals_model_dr1j(*args, **kwargs):
    return map_decals_dr1j(*args, model=True, model_gz=False, **kwargs)

def map_decals_resid_dr1j(*args, **kwargs):
    return map_decals_dr1j(*args, resid=True, model_gz=False, **kwargs)

def map_decals_nexp_dr1j(*args, **kwargs):
    return map_decals_dr1j(*args, nexp=True, model_gz=False, add_gz=True, **kwargs)

def _unwise_to_rgb(imgs, bands=[1,2], S=None, Q=None):
    import numpy as np
    img = imgs[0]
    H,W = img.shape


    if S is not None or Q is not None:
        # 
        if S is None:
            S = [1000.]*len(imgs)
        if Q is None:
            Q = 25.
        alpha = 1.5

        if len(imgs) == 2:
            w1,w2 = imgs
            S1,S2 = S
            b = w1 / S1
            r = w2 / S2
            g = (r + b) / 2.
        elif len(imgs) == 4:
            w1,w2,w3,w4 = imgs
            S1,S2,S3,S4 = S
            w1 /= S1
            w2 /= S2
            w3 /= S3
            w4 /= S4
            b = w1
            g = 0.8 * w2 + 0.2 * w3
            r = 0.4 * w2 + 0.8 * w3 + w4

        m = -2e-2
    
        r = np.maximum(0, r - m)
        g = np.maximum(0, g - m)
        b = np.maximum(0, b - m)
        I = (r+g+b)/3.
        fI = np.arcsinh(alpha * Q * I) / np.sqrt(Q)
        I += (I == 0.) * 1e-6
        R = fI * r / I
        G = fI * g / I
        B = fI * b / I
        RGB = (np.clip(np.dstack([R,G,B]), 0., 1.) * 255.).astype(np.uint8)
        return RGB

    ## FIXME
    w1,w2 = imgs
    
    rgb = np.zeros((H, W, 3), np.uint8)

    scale1 = 50.
    scale2 = 50.

    mn,mx = -1.,100.
    arcsinh = 1.
    #mn,mx = -3.,30.
    #arcsinh = None

    img1 = w1 / scale1
    img2 = w2 / scale2

    if arcsinh is not None:
        def nlmap(x):
            return np.arcsinh(x * arcsinh) / np.sqrt(arcsinh)
        #img1 = nlmap(img1)
        #img2 = nlmap(img2)
        mean = (img1 + img2) / 2.
        I = nlmap(mean)
        img1 = img1 / mean * I
        img2 = img2 / mean * I
        mn = nlmap(mn)
        mx = nlmap(mx)
    img1 = (img1 - mn) / (mx - mn)
    img2 = (img2 - mn) / (mx - mn)

    rgb[:,:,2] = (np.clip(img1, 0., 1.) * 255).astype(np.uint8)
    rgb[:,:,0] = (np.clip(img2, 0., 1.) * 255).astype(np.uint8)
    rgb[:,:,1] = rgb[:,:,0]/2 + rgb[:,:,2]/2

    return rgb

UNW = None
UNW_tree = None

def map_unwise_w1w2(*args, **kwargs):
    return map_unwise(*args, **kwargs)

def map_unwise_w3w4(*args, **kwargs):
    kwargs.update(S=[1e5, 1e6])
    return map_unwise(*args, bands=[3,4], tag='unwise-w3w4', **kwargs)

def map_unwise_w1234(*args, **kwargs):
    kwargs.update(S=[3e3, 3e3, 3e5, 1e6])
    return map_unwise(*args, bands=[1,2,3,4], tag='unwise-w1234', **kwargs)

def map_unwise(req, ver, zoom, x, y, savecache = False, ignoreCached=False,
               get_images=False,
               bands=[1,2], tag='unwise-w1w2', **kwargs):
    global UNW
    global UNW_tree

    zoom = int(zoom)
    zoomscale = 2.**zoom
    x = int(x)
    y = int(y)
    if zoom < 0 or x < 0 or y < 0 or x >= zoomscale or y >= zoomscale:
        raise RuntimeError('Invalid zoom,x,y %i,%i,%i' % (zoom,x,y))
    ver = int(ver)

    if not ver in tileversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from decals import settings

    basedir = settings.DATA_DIR
    tilefn = os.path.join(basedir, 'tiles', tag,
                          '%i/%i/%i/%i.jpg' % (ver, zoom, x, y))
    if os.path.exists(tilefn) and not ignoreCached:
        return send_file(tilefn, 'image/jpeg', expires=oneyear,
                         modsince=req.META.get('HTTP_IF_MODIFIED_SINCE'))

    if not savecache:
        import tempfile
        f,tilefn = tempfile.mkstemp(suffix='.jpg')
        os.close(f)

    try:
        wcs, W, H, zoomscale, zoom,x,y = get_tile_wcs(zoom, x, y)
    except RuntimeError as e:
        return HttpResponse(e.strerror)

    from astrometry.util.fits import fits_table
    import numpy as np
    from astrometry.libkd.spherematch import tree_build_radec, tree_search_radec
    from astrometry.util.starutil_numpy import degrees_between, arcsec_between
    from astrometry.util.resample import resample_with_wcs, OverlapError
    from astrometry.util.util import Tan
    import fitsio

    if UNW is None:
        UNW = fits_table(os.path.join(settings.UNWISE_DIR, 'allsky-atlas.fits'))
        UNW_tree = tree_build_radec(UNW.ra, UNW.dec)

    # unWISE tile size
    radius = 1.01 * np.sqrt(2.)/2. * 2.75 * 2048 / 3600.

    # leaflet tile size
    ok,ra,dec = wcs.pixelxy2radec(W/2., H/2.)
    ok,r0,d0 = wcs.pixelxy2radec(1, 1)
    ok,r1,d1 = wcs.pixelxy2radec(W, H)
    radius = radius + max(degrees_between(ra,dec, r0,d0), degrees_between(ra,dec, r1,d1))

    J = tree_search_radec(UNW_tree, ra, dec, radius)
    #print len(J), 'unWISE tiles nearby'
    
    ww = [1, W*0.25, W*0.5, W*0.75, W]
    hh = [1, H*0.25, H*0.5, H*0.75, H]

    ok,r,d = wcs.pixelxy2radec(
        [1]*len(hh) + ww          + [W]*len(hh) +        list(reversed(ww)),
        hh          + [1]*len(ww) + list(reversed(hh)) + [H]*len(ww))
    scaled = 0
    scalepat = None
    scaledir = 'unwise'

    if zoom < 11:
        # Get *actual* pixel scales at the top & bottom
        ok,r1,d1 = wcs.pixelxy2radec(W/2., H)
        ok,r2,d2 = wcs.pixelxy2radec(W/2., H-1.)
        ok,r3,d3 = wcs.pixelxy2radec(W/2., 1.)
        ok,r4,d4 = wcs.pixelxy2radec(W/2., 2.)
        # Take the min = most zoomed-in
        scale = min(arcsec_between(r1,d1, r2,d2), arcsec_between(r3,d3, r4,d4))
        
        native_scale = 2.75
        scaled = int(np.floor(np.log2(scale / native_scale)))
        print 'Zoom:', zoom, 'x,y', x,y, 'Tile pixel scale:', scale, 'Scale step:', scaled
        scaled = np.clip(scaled, 1, 7)
        dirnm = os.path.join(basedir, 'scaled', scaledir)
        scalepat = os.path.join(dirnm, '%(scale)i%(band)s', '%(tilename).3s', 'unwise-%(tilename)s-%(band)s.fits')

    basepat = os.path.join(settings.UNWISE_DIR, '%(tilename).3s', '%(tilename)s', 'unwise-%(tilename)s-%(band)s-img-u.fits')

    rimgs = [np.zeros((H,W), np.float32) for band in bands]
    rn    = np.zeros((H,W), np.uint8)

    for j in J:
        tile = UNW.coadd_id[j]

        fns = []
        for band in bands:
            bandname = 'w%i' % band
            fnargs = dict(band=bandname, tilename=tile)
            basefn = basepat % fnargs
            fn = get_scaled(scalepat, fnargs, scaled, basefn)
            fns.append(fn)

        bwcs = Tan(fns[0], 0)
        ok,xx,yy = bwcs.radec2pixelxy(r, d)
        if not np.all(ok):
            print 'Skipping tile', tile
            continue
        assert(np.all(ok))
        xx = xx.astype(np.int)
        yy = yy.astype(np.int)
        imW,imH = int(bwcs.get_width()), int(bwcs.get_height())
        # Margin
        M = 20
        xlo = np.clip(xx.min() - M, 0, imW)
        xhi = np.clip(xx.max() + M, 0, imW)
        ylo = np.clip(yy.min() - M, 0, imH)
        yhi = np.clip(yy.max() + M, 0, imH)
        if xlo >= xhi or ylo >= yhi:
            continue
        subwcs = bwcs.get_subimage(xlo, ylo, xhi-xlo, yhi-ylo)
        slc = slice(ylo,yhi), slice(xlo,xhi)

        try:
            Yo,Xo,Yi,Xi,nil = resample_with_wcs(wcs, subwcs, [], 3)
        except OverlapError:
            # print 'Resampling exception'
            # import traceback
            # print traceback.print_exc()
            continue

        for fn, rimg in zip(fns, rimgs):
            f = fitsio.FITS(fn)[0]
            img = f[slc]
            rimg[Yo,Xo] += img[Yi,Xi]
            del img, f
        rn  [Yo,Xo] += 1

    for rimg in rimgs:
        rimg /= np.maximum(rn, 1)
    del rn

    if get_images:
        return rimgs

    rgb = _unwise_to_rgb(rimgs, **kwargs)

    import pylab as plt

    trymakedirs(tilefn)

    # no jpeg output support in matplotlib in some installations...
    if True:
        import tempfile
        f,tempfn = tempfile.mkstemp(suffix='.png')
        os.close(f)
        plt.imsave(tempfn, rgb)
        print 'Wrote to temp file', tempfn
        cmd = 'pngtopnm %s | pnmtojpeg -quality 90 > %s' % (tempfn, tilefn)
        print cmd
        os.system(cmd)
        os.unlink(tempfn)
        print 'Wrote', tilefn

    return send_file(tilefn, 'image/jpeg', unlink=(not savecache))


sfd = None
halpha = None

def map_halpha(req, ver, zoom, x, y, savecache=False):
    global halpha

    from tractor.sfd import SFDMap
    if halpha is None:
        halpha = SFDMap(ngp_filename=os.path.join(settings.HALPHA_DIR,'Halpha_4096_ngp.fits'), sgp_filename=os.path.join(settings.HALPHA_DIR,'Halpha_4096_sgp.fits'))

    # Doug says: np.log10(halpha + 5) stretched to 0.5 to 2.5

    def stretch(x):
        import numpy as np
        return np.log10(x + 5)

    return map_zea(req, ver, zoom, x, y, ZEAmap=halpha, tag='halpha', savecache=savecache, vmin=0.5, vmax=2.5, stretch=stretch)


def map_sfd(req, ver, zoom, x, y, savecache=False):
    global sfd

    from tractor.sfd import SFDMap
    if sfd is None:
        sfd = SFDMap(dustdir=settings.DUST_DIR)

    return map_zea(req, ver, zoom, x, y, ZEAmap=sfd, tag='sfd', savecache=savecache)


def map_zea(req, ver, zoom, x, y, ZEAmap=None, tag=None, savecache=False, vmin=0, vmax=0.5, stretch=None):

    zoom = int(zoom)
    zoomscale = 2.**zoom
    x = int(x)
    y = int(y)
    if zoom < 0 or x < 0 or y < 0 or x >= zoomscale or y >= zoomscale:
        raise RuntimeError('Invalid zoom,x,y %i,%i,%i' % (zoom,x,y))
    ver = int(ver)


    if not ver in tileversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from decals import settings

    basedir = settings.DATA_DIR
    tilefn = os.path.join(basedir, 'tiles', tag,
                          '%i/%i/%i/%i.jpg' % (ver, zoom, x, y))

    if os.path.exists(tilefn):
        # print 'Cached:', tilefn
        return send_file(tilefn, 'image/jpeg', expires=oneyear,
                         modsince=req.META.get('HTTP_IF_MODIFIED_SINCE'))

    import numpy as np
    
    try:
        wcs, W, H, zoomscale, zoom,x,y = get_tile_wcs(zoom, x, y)
    except RuntimeError as e:
        return HttpResponse(e.strerror)

    xx,yy = np.meshgrid(np.arange(wcs.get_width()), np.arange(wcs.get_height()))
    ok,rr,dd = wcs.pixelxy2radec(xx.ravel(), yy.ravel())

    # Calling ebv function for historical reasons, works for any ZEA map.
    val = ZEAmap.ebv(rr, dd) 
    val = val.reshape(xx.shape)

    trymakedirs(tilefn)

    if not savecache:
        import tempfile
        #f,tilefn = tempfile.mkstemp(suffix='.jpg')
        f,tilefn = tempfile.mkstemp(suffix='.png')
        os.close(f)

    import pylab as plt

    # no jpeg output support in matplotlib in some installations...
    if True:
        import tempfile
        f,tempfn = tempfile.mkstemp(suffix='.png')
        os.close(f)

        if stretch is not None:
            val = stretch(val)
        plt.imsave(tempfn, val, vmin=vmin, vmax=vmax, cmap='hot')

        cmd = 'pngtopnm %s | pnmtojpeg -quality 90 > %s' % (tempfn, tilefn)
        os.system(cmd)
        os.unlink(tempfn)
        print 'Wrote', tilefn

    return send_file(tilefn, 'image/jpeg', unlink=(not savecache))


decals = {}
def _get_decals(name=None):
    global decals
    if name in decals:
        return decals[name]

    print 'Creating Decals() object for "%s"' % name

    from decals import settings
    basedir = settings.DATA_DIR
    from legacypipe.common import Decals

    if name == 'decals-dr2':
        dirnm = os.path.join(basedir, 'decals-dr2')
        d = Decals(decals_dir=dirnm)
        decals[name] = d
        return d

    name = 'decals-dr1'
    if name in decals:
        return decals[name]

    d = Decals()
    decals[name] = d
    return d

def brick_list(req):
    import json

    north = float(req.GET['north'])
    south = float(req.GET['south'])
    east  = float(req.GET['east'])
    west  = float(req.GET['west'])
    #print 'N,S,E,W:', north, south, east, west

    if east < 0:
        east += 360.
        west += 360.


    B = None

    name = req.GET.get('id', None)
    if name == 'decals-dr1k':
        from astrometry.util.fits import fits_table
        B = fits_table(os.path.join(settings.DATA_DIR, 'decals-dr1k',
                                    'decals-bricks.fits'))
    elif name == 'decals-dr1n':
        from astrometry.util.fits import fits_table
        B = fits_table(os.path.join(settings.DATA_DIR,
                                    'decals-bricks.fits'))

    D = _get_decals(name=name)
    if B is None:
        B = D.get_bricks_readonly()

    I = D.bricks_touching_radec_box(B, east, west, south, north)
    # HACK -- limit result size...
    if len(I) > 10000:
        return HttpResponse(json.dumps(dict(bricks=[])),
                            content_type='application/json')
    #I = I[:1000]
    bricks = []
    for b in B[I]:
        # brick overlap margin:
        #mdec = (0.262 * 20 / 3600.)
        #mra = mdec / np.cos(np.deg2rad(b.dec))
        mra = mdec = 0.
        bricks.append(dict(name=b.brickname,
                           poly=[[b.dec1-mdec, ra2long(b.ra1-mra)],
                                 [b.dec2+mdec, ra2long(b.ra1-mra)],
                                 [b.dec2+mdec, ra2long(b.ra2+mra)],
                                 [b.dec1-mdec, ra2long(b.ra2+mra)],
                                 ]))

    return HttpResponse(json.dumps(dict(bricks=bricks)),
                        content_type='application/json')

ccdtree = None
CCDs = None

ccdtree_dr1k = None
CCDs_dr1k = None

ccdtree_dr1n = None
CCDs_dr1n = None

ccdtree_dr2 = None
CCDs_dr2 = None

def _ccds_touching_box(north, south, east, west, Nmax=None, name=None):
    from astrometry.libkd.spherematch import tree_build_radec, tree_search_radec
    from astrometry.util.starutil_numpy import degrees_between
    import numpy as np
    global ccdtree
    global CCDs

    global ccdtree_dr1k
    global CCDs_dr1k

    global ccdtree_dr1n
    global CCDs_dr1n

    global ccdtree_dr2
    global CCDs_dr2

    if name == 'decals-dr1k':
        if ccdtree_dr1k is None:
            from astrometry.util.fits import fits_table
            CCDs_dr1k = fits_table(os.path.join(settings.DATA_DIR, 'decals-dr1k',
                                                'decals-ccds.fits'))
            ccdtree_dr1k = tree_build_radec(CCDs_dr1k.ra, CCDs_dr1k.dec)
        theCCDs = CCDs_dr1k
        theccdtree = ccdtree_dr1k

    elif name == 'decals-dr1n':
        if ccdtree_dr1n is None:
            from astrometry.util.fits import fits_table
            CCDs_dr1n = fits_table(os.path.join(settings.DATA_DIR, 'decals-ccds-dr1n.fits'))
            ccdtree_dr1n = tree_build_radec(CCDs_dr1n.ra, CCDs_dr1n.dec)
        theCCDs = CCDs_dr1n
        theccdtree = ccdtree_dr1n

    elif name == 'decals-dr2':
        if ccdtree_dr2 is None:
            from astrometry.util.fits import fits_table
            CCDs_dr2 = fits_table(os.path.join(settings.DATA_DIR, 'decals-dr2', 'decals-ccds.fits'))
            ccdtree_dr2 = tree_build_radec(CCDs_dr2.ra, CCDs_dr2.dec)
        theCCDs = CCDs_dr2
        theccdtree = ccdtree_dr2

    else:
        if ccdtree is None:
            D = _get_decals(name=name)
            CCDs = D.get_ccds()
            ccdtree = tree_build_radec(CCDs.ra, CCDs.dec)
        theCCDs = CCDs
        theccdtree = ccdtree
            

    dec = (north + south) / 2.
    c = (np.cos(np.deg2rad(east)) + np.cos(np.deg2rad(west))) / 2.
    s = (np.sin(np.deg2rad(east)) + np.sin(np.deg2rad(west))) / 2.
    ra  = np.rad2deg(np.arctan2(s, c))

    # image size
    radius = np.hypot(2048, 4096) * 0.262/3600. / 2.
    # RA,Dec box size
    radius = radius + degrees_between(east, north, west, south) / 2.

    J = tree_search_radec(theccdtree, ra, dec, radius)

    if Nmax is not None:
        # limit result size
        J = J[:Nmax]

    return theCCDs[J]

def ccd_list(req):
    import json
    from astrometry.util.util import Tan
    import numpy as np

    north = float(req.GET['north'])
    south = float(req.GET['south'])
    east  = float(req.GET['east'])
    west  = float(req.GET['west'])
    #print 'N,S,E,W:', north, south, east, west

    name = req.GET.get('id', None)

    CCDS = _ccds_touching_box(north, south, east, west, Nmax=10000, name=name)

    ccdname = lambda c: '%i-%s-%s' % (c.expnum, c.extname.strip(), c.filter)

    if name == 'decals-dr2':
        ccdname = lambda c: '%i-%s-%s' % (c.expnum, c.ccdname.strip(), c.filter)
        decals = _get_decals(name)
        CCDS.cut(decals.photometric_ccds(CCDS))

    CCDS.cut(np.lexsort((CCDS.expnum, CCDS.filter)))

    ccds = []
    for c in CCDS:
        wcs = Tan(*[float(x) for x in [
            c.ra_bore, c.dec_bore, c.crpix1, c.crpix2, c.cd1_1, c.cd1_2,
            c.cd2_1, c.cd2_2, c.width, c.height]])
        x = np.array([1, 1, c.width, c.width])
        y = np.array([1, c.height, c.height, 1])
        r,d = wcs.pixelxy2radec(x, y)
        ccds.append(dict(name=ccdname(c),
                         poly=zip(d, ra2long(r))))

    return HttpResponse(json.dumps(dict(ccds=ccds)),
                        content_type='application/json')
    
def ccd_detail(req, name, ccd):
    import numpy as np
    #ccd = req.GET['ccd']
    words = ccd.split('-')
    assert(len(words) == 3)
    expnum = int(words[0], 10)
    assert(words[1][0] in 'NS')
    ns = words[1][0]
    chipnum = int(words[1][1:], 10)
    extname = '%s%i' % (ns,chipnum)

    D = _get_decals(name=name)
    CCDs = D.get_ccds()

    if name == 'decals-dr2':
        I = np.flatnonzero((CCDs.expnum == expnum) * 
                           np.array([n.strip() == extname for n in CCDs.ccdname]))
        about = lambda ccd, c: 'CCD %s, image %s, hdu %i; exptime %.1f sec, seeing %.1f arcsec' % (ccd, c.image_filename, c.image_hdu, c.exptime, c.seeing)
    else:
        I = np.flatnonzero((CCDs.expnum == expnum) * 
                           np.array([n.strip() == extname for n in CCDs.extname]))
        about = lambda ccd, c: 'CCD %s, image %s, hdu %i; exptime %.1f sec, seeing %.1f arcsec' % (ccd, c.cpimage, c.cpimage_hdu, c.exptime, c.fwhm*0.262)
    assert(len(I) == 1)

    c = CCDs[I[0]]
    return HttpResponse(about(ccd, c))

def nil(req):
    pass

def brick_detail(req, brickname):
    #brickname = req.GET['brick']
    return HttpResponse('Brick ' + brickname)

def cat_vcc(req, ver):
    import json
    tag = 'ngc'
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])

    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from astrometry.util.fits import fits_table, merge_tables
    import numpy as np
    from decals import settings

    TT = []
    T = fits_table(os.path.join(settings.DATA_DIR, 'virgo-cluster-cat-2.fits'))
    print len(T), 'in VCC 2; ra', ralo, rahi, 'dec', declo, dechi
    T.cut((T.ra > ralo) * (T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    print len(T), 'in cut'
    TT.append(T)

    T = fits_table(os.path.join(settings.DATA_DIR, 'virgo-cluster-cat-3.fits'))
    print len(T), 'in VCC 3; ra', ralo, rahi, 'dec', declo, dechi
    T.cut((T.ra > ralo) * (T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    print len(T), 'in cut'
    T.evcc_id = np.array(['-']*len(T))
    T.rename('id', 'vcc_id')
    TT.append(T)
    T = merge_tables(TT)

    rd = list((float(r),float(d)) for r,d in zip(T.ra, T.dec))
    names = []

    for t in T:
        evcc = t.evcc_id.strip()
        vcc = t.vcc_id.strip()
        ngc = t.ngc.strip()
        nms = []
        if evcc != '-':
            nms.append('EVCC ' + evcc)
        if vcc != '-':
            nms.append('VCC ' + vcc)
        if ngc != '-':
            nms.append('NGC ' + ngc)
        names.append(' / '.join(nms))

    return HttpResponse(json.dumps(dict(rd=rd, name=names)),
                        content_type='application/json')

def cat_spec(req, ver):
    import json
    tag = 'ngc'
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])

    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from astrometry.util.fits import fits_table, merge_tables
    import numpy as np
    from decals import settings

    TT = []
    T = fits_table(os.path.join(settings.DATA_DIR, 'specObj-dr12-trim-2.fits'))
    print len(T), 'spectra'
    if ralo > rahi:
        # RA wrap
        T.cut(np.logical_or(T.ra > ralo, T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    else:
        T.cut((T.ra > ralo) * (T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    print len(T), 'in cut'

    rd = list((float(r),float(d)) for r,d in zip(T.ra, T.dec))
    names = [t.strip() for t in T.label]
    mjd   = [int(x) for x in T.mjd]
    fiber = [int(x) for x in T.fiberid]
    plate = [int(x) for x in T.plate]

    return HttpResponse(json.dumps(dict(rd=rd, name=names, mjd=mjd, fiber=fiber, plate=plate)),
                        content_type='application/json')


def cat_ngc(req, ver, zoom, x, y):
    import json
    tag = 'ngc'
    zoom = int(zoom)
    try:
        wcs, W, H, zoomscale, zoom,x,y = get_tile_wcs(zoom, x, y)
    except RuntimeError as e:
        return HttpResponse(e.strerror)
    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from astrometry.util.fits import fits_table
    import numpy as np
    from astrometry.libkd.spherematch import match_radec
    from astrometry.util.starutil_numpy import degrees_between, arcsec_between
    from astrometry import catalogs

    ok,ra,dec = wcs.pixelxy2radec(W/2., H/2.)
    ok,r0,d0 = wcs.pixelxy2radec(1, 1)
    ok,r1,d1 = wcs.pixelxy2radec(W, H)
    radius = max(degrees_between(ra,dec, r0,d0),
                 degrees_between(ra,dec, r1,d1))

    T = fits_table(os.path.join(os.path.dirname(catalogs.__file__), 'ngc2000.fits'))

    I,J,d = match_radec(ra, dec, T.ra, T.dec, radius * 1.1)
    
    rd = list((float(r),float(d)) for r,d in zip(T.ra[J], T.dec[J]))
    names = ['NGC %i' % i for i in T.ngcnum[J]]
    radius = list(float(x) for x in T.radius[J] * 3600.)

    return HttpResponse(json.dumps(dict(rd=rd, name=names,
                                        radiusArcsec=radius)),
                        content_type='application/json')

def cat_decals_dr1j(req, ver, zoom, x, y, tag='decals-dr1j'):
    return cat_decals(req, ver, zoom, x, y, tag=tag, docache=False)

def cat_decals_dr2(req, ver, zoom, x, y, tag='decals-dr2'):
    return cat_decals(req, ver, zoom, x, y, tag=tag, docache=False)

def cat_decals(req, ver, zoom, x, y, tag='decals', docache=True):
    import json
    zoom = int(zoom)
    if zoom < 12:
        return HttpResponse(json.dumps(dict(rd=[])),
                            content_type='application/json')

    from astrometry.util.fits import fits_table, merge_tables
    import numpy as np

    try:
        wcs, W, H, zoomscale, zoom,x,y = get_tile_wcs(zoom, x, y)
    except RuntimeError as e:
        return HttpResponse(e.strerror)
    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    basedir = settings.DATA_DIR
    if docache:
        cachefn = os.path.join(basedir, 'cats-cache', tag,
                               '%i/%i/%i/%i.cat.json' % (ver, zoom, x, y))
        if os.path.exists(cachefn):
            # print 'Cached:', cachefn
            return send_file(cachefn, 'application/json',
                             modsince=req.META.get('HTTP_IF_MODIFIED_SINCE'),
                             expires=oneyear)
    else:
        import tempfile
        f,cachefn = tempfile.mkstemp(suffix='.jpg')
        os.close(f)

    cat,hdr = _get_decals_cat(wcs, tag=tag)

    if cat is None:
        rd = []
        types = []
        fluxes = []
        bricknames = []
        objids = []
        nobs = []
    else:
        #print 'All catalogs:'
        #cat.about()
        rd = zip(cat.ra, cat.dec)
        types = list([t[0] for t in cat.get('type')])
        fluxes = [dict(g=float(g), r=float(r), z=float(z))
                  for g,r,z in zip(cat.decam_flux[:,1], cat.decam_flux[:,2],
                                   cat.decam_flux[:,4])]
        nobs = [dict(g=int(g), r=int(r), z=int(z))
                for g,r,z in zip(cat.decam_nobs[:,1], cat.decam_nobs[:,2],
                                 cat.decam_nobs[:,4])]
        bricknames = list(cat.brickname)
        objids = [int(x) for x in cat.objid]

    json = json.dumps(dict(rd=rd, sourcetype=types, fluxes=fluxes, nobs=nobs,
                                 bricknames=bricknames, objids=objids))
    if docache:
        trymakedirs(cachefn)

    f = open(cachefn, 'w')
    f.write(json)
    f.close()
    return send_file(cachefn, 'application/json', expires=oneyear)

def _get_decals_cat(wcs, tag='decals'):
    from decals import settings
    from astrometry.util.fits import fits_table, merge_tables

    basedir = settings.DATA_DIR
    H,W = wcs.shape
    # print 'WCS shape:', H,W
    X = wcs.pixelxy2radec([1,1,1,W/2,W,W,W,W/2],
                            [1,H/2,H,H,H,H/2,1,1])
    r,d = X[-2:]
    catpat = os.path.join(basedir, 'cats', tag, '%(brickname).3s',
                          'tractor-%(brickname)s.fits')
    # FIXME (name)
    D = _get_decals()
    B = D.get_bricks_readonly()
    I = D.bricks_touching_radec_box(B, r.min(), r.max(), d.min(), d.max())

    cat = []
    hdr = None
    for brickid,brickname in zip(B.brickid[I], B.brickname[I]):
        fnargs = dict(brick=brickid, brickname=brickname)
        catfn = catpat % fnargs
        if not os.path.exists(catfn):
            print 'Does not exist:', catfn
            continue
        print 'Reading catalog', catfn
        T = fits_table(catfn)
        # FIXME -- all False
        # print 'brick_primary', np.unique(T.brick_primary)
        # T.cut(T.brick_primary)
        ok,xx,yy = wcs.radec2pixelxy(T.ra, T.dec)
        #print 'xx,yy', xx.min(), xx.max(), yy.min(), yy.max()
        T.cut((xx > 0) * (yy > 0) * (xx < W) * (yy < H))
        # print 'kept', len(T), 'from', catfn
        cat.append(T)
        if hdr is None:
            hdr = T.get_header()
    if len(cat) == 0:
        cat = None
    else:
        cat = merge_tables(cat)

    return cat,hdr

def map_coadd_bands(req, ver, zoom, x, y, bands, tag, imagedir,
                    wcs=None,
                    imagetag='image2', rgbkwargs={},
                    bricks=None,
                    savecache = True, forcecache = False,
                    return_if_not_found=False, model_gz=False,
                    modeldir=None, scaledir=None, get_images=False,
                    ignoreCached=False, add_gz=False, filename=None
                    ):
    from decals import settings

    zoom = int(zoom)
    zoomscale = 2.**zoom
    x = int(x)
    y = int(y)
    if zoom < 0 or x < 0 or y < 0 or x >= zoomscale or y >= zoomscale:
        raise RuntimeError('Invalid zoom,x,y %i,%i,%i' % (zoom,x,y))
    ver = int(ver)

    if not ver in tileversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    basedir = settings.DATA_DIR
    tilefn = os.path.join(basedir, 'tiles', tag,
                          '%i/%i/%i/%i.jpg' % (ver, zoom, x, y))
    if os.path.exists(tilefn) and not ignoreCached:
        print 'Cached:', tilefn
        return send_file(tilefn, 'image/jpeg', expires=oneyear,
                         modsince=req.META.get('HTTP_IF_MODIFIED_SINCE'),
                         filename=filename)
    else:
        print 'Tile image does not exist:', tilefn
    from astrometry.util.resample import resample_with_wcs, OverlapError
    from astrometry.util.util import Tan
    from legacypipe.common import get_rgb
    import numpy as np
    import fitsio

    if wcs is None:
        try:
            wcs, W, H, zoomscale, zoom,x,y = get_tile_wcs(zoom, x, y)
        except RuntimeError as e:
            return HttpResponse(e.strerror)
    else:
        W = wcs.get_width()
        H = wcs.get_height()

    basepat = os.path.join(basedir, 'coadd', imagedir, '%(brickname).3s',
                           '%(brickname)s',
                           'decals-%(brickname)s-' + imagetag + '-%(band)s.fits')
    if modeldir is not None:
        modbasepat = os.path.join(basedir, 'coadd', modeldir, '%(brickname).3s',
                                  '%(brickname)s',
                                  'decals-%(brickname)s-' + imagetag + '-%(band)s.fits')
    else:
        modbasepat = basepat
    if model_gz and imagetag == 'model':
        modbasepat += '.gz'
    #print 'add_gz:', add_gz
    if add_gz:
        basepat += '.gz'
    #print 'basepat:', basepat

    scaled = 0
    scalepat = None
    if scaledir is None:
        scaledir = imagedir
    if zoom < 14:
        scaled = (14 - zoom)
        scaled = np.clip(scaled, 1, 8)
        #print 'Scaled-down:', scaled
        dirnm = os.path.join(basedir, 'scaled', scaledir)
        scalepat = os.path.join(dirnm, '%(scale)i%(band)s', '%(brickname).3s', imagetag + '-%(brickname)s-%(band)s.fits')
        
    D = _get_decals()
    if bricks is None:
        B = D.get_bricks_readonly()
    else:
        B = bricks

    rlo,d = wcs.pixelxy2radec(W, H/2)[-2:]
    rhi,d = wcs.pixelxy2radec(1, H/2)[-2:]
    r,d1 = wcs.pixelxy2radec(W/2, 1)[-2:]
    r,d2 = wcs.pixelxy2radec(W/2, H)[-2:]
    dlo = min(d1, d2)
    dhi = max(d1, d2)
    I = D.bricks_touching_radec_box(B, rlo, rhi, dlo, dhi)
    print len(I), 'bricks touching zoom', zoom, 'x,y', x,y, 'RA', rlo,rhi, 'Dec', dlo,dhi

    if len(I) == 0:
        if get_images:
            return None
        from django.http import HttpResponseRedirect
        if forcecache:
            # create symlink to blank.jpg!
            trymakedirs(tilefn)
            src = os.path.join(settings.STATIC_ROOT, 'blank.jpg')
            if os.path.exists(tilefn):
                os.unlink(tilefn)
            os.symlink(src, tilefn)
            print 'Symlinked', tilefn, '->', src
        return HttpResponseRedirect(settings.STATIC_URL + 'blank.jpg')

    r,d = wcs.pixelxy2radec([1,1,1,W/2,W,W,W,W/2],
                            [1,H/2,H,H,H,H/2,1,1])[-2:]

    foundany = False
    rimgs = []
    for band in bands:
        rimg = np.zeros((H,W), np.float32)
        rn   = np.zeros((H,W), np.uint8)
        for i,brickid,brickname in zip(I,B.brickid[I], B.brickname[I]):
            has = getattr(B, 'has_%s' % band, None)
            if has is not None and not has[i]:
                # No coverage for band in this brick.
                print 'Brick', brickname, 'has no', band, 'band'
                continue

            fnargs = dict(band=band, brick=brickid, brickname=brickname)

            if imagetag == 'resid':
                basefn = basepat % fnargs

                modbasefn = modbasepat % fnargs
                modbasefn = modbasefn.replace('resid', 'model')
                if model_gz:
                    modbasefn += '.gz'

                if scalepat is None:
                    imscalepat = None
                    modscalepat = None
                else:
                    imscalepat = scalepat.replace('resid', 'image')
                    modscalepat = scalepat.replace('resid', 'model')
                imbasefn = basefn.replace('resid', 'image')
                imfn = get_scaled(imscalepat, fnargs, scaled, imbasefn)
                # print 'imfn', imfn
                modfn = get_scaled(modscalepat, fnargs, scaled, modbasefn)
                # print 'modfn', modfn
                fn = imfn

            else:
                basefn = basepat % fnargs
                fn = get_scaled(scalepat, fnargs, scaled, basefn)
            if fn is None:
                # print 'Filename:', fn
                print 'not found: brick', brickname, 'band', band, 'with basefn', basefn
                savecache = False
                continue
            if not os.path.exists(fn):
                print 'Does not exist:', fn
                # dr = fn
                # for x in range(10):
                #     dr = os.path.dirname(dr)
                #     print 'dir', dr, 'exists?', os.path.exists(dr)
                savecache = False
                continue
            try:
                #bwcs = Tan(fn, 0)
                bwcs = _read_tan_wcs(fn, 0)
            except:
                print 'Failed to read WCS:', fn
                savecache = False
                import traceback
                import sys
                traceback.print_exc(None, sys.stdout)
                continue

            foundany = True
            print 'Reading', fn
            ok,xx,yy = bwcs.radec2pixelxy(r, d)
            xx = xx.astype(np.int)
            yy = yy.astype(np.int)
            #print 'x,y', x,y
            imW,imH = int(bwcs.get_width()), int(bwcs.get_height())
            M = 10
            #print 'brick coordinates of tile: x', xx.min(), xx.max(), 'y', yy.min(), yy.max()
            xlo = np.clip(xx.min() - M, 0, imW)
            xhi = np.clip(xx.max() + M, 0, imW)
            ylo = np.clip(yy.min() - M, 0, imH)
            yhi = np.clip(yy.max() + M, 0, imH)
            #print 'brick size', imW, 'x', imH
            #print 'clipped brick coordinates: x', xlo, xhi, 'y', ylo,yhi
            if xlo >= xhi or ylo >= yhi:
                #print 'skipping'
                continue

            subwcs = bwcs.get_subimage(xlo, ylo, xhi-xlo, yhi-ylo)
            slc = slice(ylo,yhi), slice(xlo,xhi)
            try:
                f = fitsio.FITS(fn)[0]
                img = f[slc]
                del f

                if imagetag == 'resid':
                    f = fitsio.FITS(modfn)[0]
                    mod = f[slc]
                    del f
                    img = img - mod
                
            except:
                print 'Failed to read image and WCS:', fn
                savecache = False
                import traceback
                import sys
                traceback.print_exc(None, sys.stdout)
                continue
            #print 'Subimage shape', img.shape
            #print 'Sub-WCS shape', subwcs.get_height(), subwcs.get_width()
            try:
                Yo,Xo,Yi,Xi,nil = resample_with_wcs(wcs, subwcs, [], 3)
            except OverlapError:
                print 'Resampling exception'
                #import traceback
                #traceback.print_exc()
                continue

            # print 'Resampling', len(Yo), 'pixels'
            # print 'out range x', Xo.min(), Xo.max(), 'y', Yo.min(), Yo.max()
            # print 'in  range x', Xi.min(), Xi.max(), 'y', Yi.min(), Yi.max()
            
            rimg[Yo,Xo] += img[Yi,Xi]
            rn  [Yo,Xo] += 1
        rimg /= np.maximum(rn, 1)
        rimgs.append(rimg)
        # print 'Band', band, ': total of', rn.sum(), 'pixels, range', rimg.min(), rimg.max()

    #if return_if_not_found and not foundany:
    if return_if_not_found and not savecache:
        return

    if get_images:
        return rimgs

    rgb = get_rgb(rimgs, bands, **rgbkwargs)

    if forcecache:
        savecache = True

    if savecache:
        trymakedirs(tilefn)
    else:
        import tempfile
        f,tilefn = tempfile.mkstemp(suffix='.jpg')
        os.close(f)

    #import matplotlib
    #matplotlib.use('Agg')
    import pylab as plt

    # no jpeg output support in matplotlib in some installations...
    if False:
        import tempfile
        f,tempfn = tempfile.mkstemp(suffix='.png')
        os.close(f)
        plt.imsave(tempfn, rgb)
        cmd = 'pngtopnm %s | pnmtojpeg -quality 90 > %s' % (tempfn, tilefn)
        os.system(cmd)
        os.unlink(tempfn)
        print 'Wrote', tilefn
    else:
        plt.imsave(tilefn, rgb)
        print 'Wrote', tilefn

    return send_file(tilefn, 'image/jpeg', unlink=(not savecache),
                     filename=filename)



def cutouts(req):
    from astrometry.util.util import Tan
    from astrometry.util.starutil_numpy import degrees_between
    import numpy as np
    from legacypipe.common import wcs_for_brick

    ra = float(req.GET['ra'])
    dec = float(req.GET['dec'])

    # half-size in DECam pixels
    size = 50
    W,H = size*2, size*2
    
    pixscale = 0.262 / 3600.
    wcs = Tan(*[float(x) for x in [
        ra, dec, size+0.5, size+0.5, -pixscale, 0., 0., pixscale, W, H]])

    nil,north = wcs.pixelxy2radec(size+0.5, H)
    nil,south = wcs.pixelxy2radec(size+0.5, 1)
    west,nil  = wcs.pixelxy2radec(1, size+0.5)
    east,nil  = wcs.pixelxy2radec(W, size+0.5)
    
    CCDs = _ccds_touching_box(north, south, east, west)

    print len(CCDs), 'CCDs'

    CCDs = CCDs[np.lexsort((CCDs.extname, CCDs.expnum, CCDs.filter))]

    ccds = []
    #for c in CCDs:
    for i in range(len(CCDs)):
        c = CCDs[i]

        try:
            from legacypipe.decam import DecamImage
            c.cpimage = _get_image_filename(c)
            dim = DecamImage(c)
            wcs = dim.read_wcs()
        except:
            import traceback
            traceback.print_exc()
            
            wcs = Tan(*[float(x) for x in [
                c.ra_bore, c.dec_bore, c.crpix1, c.crpix2, c.cd1_1, c.cd1_2,
                c.cd2_1, c.cd2_2, c.width, c.height]])
        ok,x,y = wcs.radec2pixelxy(ra, dec)
        x = int(np.round(x-1))
        y = int(np.round(y-1))
        if x < -size or x >= c.width+size or y < -size or y >= c.height+size:
            continue

        #print 'CCD', c
        #c = dict([(k,c.get(k)) for k in c.columns()])
        #print 'CCD', c
        ccds.append((c, x, y))

    #print 'CCDS:', ccds

    D = _get_decals()
    B = D.get_bricks_readonly()

    I = np.flatnonzero((B.ra1  <= ra)  * (B.ra2  >= ra) *
                       (B.dec1 <= dec) * (B.dec2 >= dec))
    brick = B[I[0]]
    bwcs = wcs_for_brick(brick)
    ok,brickx,bricky = bwcs.radec2pixelxy(ra, dec)
    brick = brick.to_dict()
    
    from django.shortcuts import render
    from django.core.urlresolvers import reverse

    #url = req.build_absolute_uri('/') + reverse('cutout_panels',
    #                                            kwargs=dict(expnum='%i',
    #                                                      extname='%s'))

    from decals import settings

    url = req.build_absolute_uri('/') + settings.ROOT_URL + '/cutout_panels/%i/%s/'

    print 'URL', url

    # Deployment: http://{s}.DOMAIN/...
    url = url.replace('://www.', '://')
    url = url.replace('://', '://%s.')

    domains = ['a','b','c','d']

    print 'URL', url
    ccdsx = []
    for i,(ccd,x,y) in enumerate(ccds):
        fn = ccd.cpimage.replace(settings.DATA_DIR + '/', '')
        ccdsx.append(('CCD %s %i %s x,y %i,%i<br/><small>(%s [%i])</small>' % (ccd.filter, ccd.expnum, ccd.extname, x, y, fn, ccd.cpimage_hdu),
                      url % (domains[i%len(domains)], int(ccd.expnum), ccd.extname) + '?x=%i&y=%i' % (x,y)))

    return render(req, 'cutouts.html',
                  dict(ra=ra, dec=dec,
                       ccds=ccdsx,
                       brick=brick,
                       brickx=brickx,
                       bricky=bricky,
                       ))

def cat_plot(req):
    import pylab as plt
    import numpy as np
    from astrometry.util.util import Tan
    from legacypipe.sdss import get_sdss_sources
    from decals import settings

    ra = float(req.GET['ra'])
    dec = float(req.GET['dec'])

    ver = float(req.GET.get('ver',2))

    # half-size in DECam pixels
    size = 50
    W,H = size*2, size*2
    
    pixscale = 0.262 / 3600.
    wcs = Tan(*[float(x) for x in [
        ra, dec, size+0.5, size+0.5, -pixscale, 0., 0., pixscale, W, H]])

    M = 10
    margwcs = wcs.get_subimage(-M, -M, W+2*M, H+2*M)

    cat,hdr = _get_decals_cat(margwcs, tag='decals-dr1j')

    # FIXME
    nil,sdss = get_sdss_sources('r', margwcs,
                                photoobjdir=os.path.join(settings.DATA_DIR, 'sdss'),
                                local=True)
    import tempfile
    f,tempfn = tempfile.mkstemp(suffix='.png')
    os.close(f)

    f = plt.figure(figsize=(2,2))
    f.subplots_adjust(left=0.01, bottom=0.01, top=0.99, right=0.99)
    f.clf()
    ax = f.add_subplot(111, xticks=[], yticks=[])
    if cat is not None:
        ok,x,y = wcs.radec2pixelxy(cat.ra, cat.dec)
        # matching the plot colors in index.html
        # cc = dict(S=(0x9a, 0xfe, 0x2e),
        #           D=(0xff, 0, 0),
        #           E=(0x58, 0xac, 0xfa),
        #           C=(0xda, 0x81, 0xf5))
        cc = dict(PSF =(0x9a, 0xfe, 0x2e),
                  DEV =(0xff, 0, 0),
                  EXP =(0x58, 0xac, 0xfa),
                  COMP=(0xda, 0x81, 0xf5))
        ax.scatter(x, y, s=50, c=[[float(x)/255. for x in cc[t.strip()]] for t in cat.type])
    if sdss is not None:
        ok,x,y = wcs.radec2pixelxy(sdss.ra, sdss.dec)
        ax.scatter(x, y, s=30, marker='x', c='k')
    ax.axis([0, W, 0, H])
    f.savefig(tempfn)

    return send_file(tempfn, 'image/png', unlink=True,
                     expires=0)


def _get_ccd(expnum, extname):
    import numpy as np
    # Not ideal... look up local CP image name from expnum.
    global CCDs
    if CCDs is None:
        D = _get_decals()
        CCDs = D.get_ccds()
    expnum = int(expnum, 10)
    extname = str(extname)
    I = np.flatnonzero((CCDs.expnum == expnum) * (CCDs.extname == extname))
    assert(len(I) == 1)
    ccd = CCDs[I[0]]
    return ccd

def _get_image_filename(ccd):
    from decals import settings
    basedir = settings.DATA_DIR
    fn = ccd.cpimage.strip()
    # drop 'decals/' off the front...
    fn = fn.replace('decals/','')
    fn = os.path.join(basedir, fn)
    return fn

def _get_image_slice(fn, hdu, x, y, size=50):
    import fitsio
    img = fitsio.FITS(fn)[hdu]
    H,W = img.get_info()['dims']
    if x < size:
        xstart = size - x
    else:
        xstart = 0
    if y < size:
        ystart = size - y
    else:
        ystart = 0
    slc = slice(max(y-size, 0), min(y+size, H)), slice(max(x-size, 0), min(x+size, W))
    print 'Image slice:', slc
    img = img[slc]
    return img,slc,xstart,ystart

def cutout_panels(req, expnum=None, extname=None, name=None):
    import pylab as plt
    import numpy as np

    x = int(req.GET['x'], 10)
    y = int(req.GET['y'], 10)
    ccd = _get_ccd(expnum, extname)

    fn = _get_image_filename(ccd)
    if not os.path.exists(fn):
        #print 'NO IMAGE:', fn
        #print 'rsync -Rrv carver:tractor/decals/images/./' + fn.replace('/home/dstn/decals-web/data/images/', '') + ' data/images'
        return HttpResponse('no such image: ' + fn)

    wfn = fn.replace('ooi', 'oow')
    if not os.path.exists(wfn):
        #cmd = 'rsync -Rrv carver:tractor/decals/images/./' + wfn.replace('/home/dstn/decals-web/data/images/', '') + ' data/images'
        #print '\n' + cmd + '\n'
        #os.system(cmd)
        #if not os.path.exists(wfn):
        return HttpResponse('no such image: ' + wfn)

    # half-size in DECam pixels -- must match cutouts():size
    size = 50
    img,slc,xstart,ystart = _get_image_slice(fn, ccd.cpimage_hdu, x, y, size=size)

    from legacypipe.decam import DecamImage
    from legacypipe.desi_common import read_fits_catalog
    from tractor import Tractor

    ccd.cpimage = fn
    im = DecamImage(ccd)
    D = _get_decals(name=name)
    tim = im.get_tractor_image(decals, slc=slc, tiny=1, const2psf=True, pvwcs=True)

    if tim is None:
        img = np.zeros((0,0))

    mn,mx = -1, 100
    arcsinh = 1.
    cmap = 'gray'
    pad = True

    scales = dict(g = (2, 0.0066),
                  r = (1, 0.01),
                  z = (0, 0.025),
                  )
    rows,cols = 1,5
    f = plt.figure(figsize=(cols,rows))
    f.clf()
    f.subplots_adjust(left=0.002, bottom=0.02, top=0.995, right=0.998,
                      wspace=0.02, hspace=0)

    imgs = []

    img = tim.getImage()
    imgs.append((img,None))
    
    M = 10
    margwcs = tim.subwcs.get_subimage(-M, -M, int(tim.subwcs.get_width())+2*M, int(tim.subwcs.get_height())+2*M)
    for dr in ['dr1j']:
        cat,hdr = _get_decals_cat(margwcs, tag='decals-%s' % dr)
        if cat is None:
            tcat = []
        else:
            cat.shapedev = np.vstack((cat.shapedev_r, cat.shapedev_e1, cat.shapedev_e2)).T
            cat.shapeexp = np.vstack((cat.shapeexp_r, cat.shapeexp_e1, cat.shapeexp_e2)).T
            tcat = read_fits_catalog(cat, hdr=hdr)
        tr = Tractor([tim], tcat)
        img = tr.getModelImage(0)
        imgs.append((img,None))

        img = tr.getChiImage(0)
        imgs.append((img, dict(mn=-5,mx=5, arcsinh = None, scale = 1.)))

    th,tw = tim.shape
    pp = tim.getPsf().getPointSourcePatch(tw/2., th/2.)
    img = np.zeros(tim.shape, np.float32)
    pp.addTo(img)
    imgs.append((img, dict(scale=0.0001, cmap='hot')))
    
    from tractor.psfex import PsfEx
    from tractor.patch import Patch
    # HACK hard-coded image sizes.
    thepsf = PsfEx(im.psffn, 2046, 4096)
    psfim = thepsf.instantiateAt(x, y)
    img = np.zeros(tim.shape, np.float32)
    h,w = tim.shape
    ph,pw = psfim.shape
    patch = Patch((w-pw)/2., (h-ph)/2., psfim)
    patch.addTo(img)
    imgs.append((img, dict(scale = 0.0001, cmap = 'hot')))

    for i,(img,d) in enumerate(imgs):

        mn,mx = -5, 100
        arcsinh = 1.
        cmap = 'gray'
        nil,scale = scales[ccd.filter]
        pad = True

        if d is not None:
            if 'mn' in d:
                mn = d['mn']
            if 'mx' in d:
                mx = d['mx']
            if 'arcsinh' in d:
                arcsinh = d['arcsinh']
            if 'cmap' in d:
                cmap = d['cmap']
            if 'scale' in d:
                scale = d['scale']

        img = img / scale
        if arcsinh is not None:
            def nlmap(x):
                return np.arcsinh(x * arcsinh) / np.sqrt(arcsinh)
            img = nlmap(img)
            mn = nlmap(mn)
            mx = nlmap(mx)

        img = (img - mn) / (mx - mn)
        if pad:
            ih,iw = img.shape
            padimg = np.zeros((2*size,2*size), img.dtype) + 0.5
            print 'Image shape:', img.shape, 'pad shape:', padimg.shape
            padimg[ystart:ystart+ih, xstart:xstart+iw] = img
            img = padimg

        ax = f.add_subplot(rows, cols, i+1, xticks=[], yticks=[])
        # the chips are turned sideways :)
        #plt.imshow(np.rot90(np.clip(img, 0, 1), k=3), cmap=cmap,
        #           interpolation='nearest', origin='lower')
        ax.imshow(np.rot90(np.clip(img, 0, 1).T, k=2), cmap=cmap,
                   interpolation='nearest', origin='lower')
        #ax.xticks([]); ax.yticks([])

    import tempfile
    ff,tilefn = tempfile.mkstemp(suffix='.jpg')
    os.close(ff)

    f.savefig(tilefn)
    f.clf()
    del f
    
    return send_file(tilefn, 'image/jpeg', unlink=True,
                     expires=3600)




if __name__ == '__main__':
    class duck(object):
        pass

    import os
    os.environ['DJANGO_SETTINGS_MODULE'] = 'decals.settings'
    
    ver = 1
    zoom,x,y = 2, 1, 1
    req = duck()
    req.META = dict()
    map_unwise_w1w2(req, ver, zoom, x, y, savecache=True, ignoreCached=True)
