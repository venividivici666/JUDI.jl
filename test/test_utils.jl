using JUDI.TimeModeling, ArgParse, Images

export setup_model, parse_commandline, setup_geom

"""
Simple 2D model setup used for the tests.
"""

function smooth(v, sigma=3)
    return Float32.(imfilter(v,  Kernel.gaussian(sigma)))
end

function setup_model(tti=false, nlayer=2)
    ## Set up model structure
    n = (301, 151)   # (x,y,z) or (x,z)
    d = (10., 10.)	
    o = (0., 0.)	
    
    v = ones(Float32,n) .* 1.5f0	
    vp_i = range(1.5f0, 3.5f0, length=nlayer)	
    for i in range(2, nlayer, step=1)	
        v[:, (i-1)*Int(floor(n[2] / nlayer)) + 1:end] .= vp_i[i]  # Bottom velocity	
    end

    # Velocity [km/s]
    v = ones(Float32,n) .+ 0.5f0
    v[:,Int(round(end/2)):end] .= 3.5f0
    v0 = smooth(v, 10)
    rho0 = (v .+ .5f0) ./ 2
    # Slowness squared [s^2/km^2]
    m = (1f0 ./ v).^2
    m0 = (1f0 ./ v0).^2
    dm = vec(m - m0)

    # Setup model structure
    if tti
        println("TTI Model")
        epsilon = smooth((v0[:, :] .- 1.5f0)/12f0, 3)
        delta =  smooth((v0[:, :] .- 1.5f0)/14f0, 3)
        theta =  smooth((v0[:, :] .- 1.5f0)/4, 3)
        model0 = Model_TTI(n,d,o,m0; epsilon=epsilon, delta=delta, theta=theta)
        model = Model_TTI(n,d,o,m; epsilon=epsilon, delta=delta, theta=theta)
    else
        model = Model(n,d,o,m,rho=rho0)
        model0 = Model(n,d,o,m0,rho=rho0)
    end

    return model, model0, dm
end

function setup_geom(model)
    ## Set up receiver geometry
    nsrc = 1
    nxrec = model.n[1] - 2
    xrec = range(model.d[1], stop=(model.n[1]-2)*model.d[1], length=nxrec)
    yrec = 0f0
    zrec = range(50f0, stop=50f0, length=nxrec)

    # receiver sampling and recording time
    time = 1500f0   # receiver recording time [ms]
    dt = 1f0    # receiver sampling interval [ms]

    # Set up receiver structure
    recGeometry = Geometry(xrec, yrec, zrec; dt=dt, t=time, nsrc=nsrc)

    ## Set up source geometry (cell array with source locations for each shot)
    xsrc = convertToCell([.5f0*(model.n[1]-1)*model.d[1]])
    ysrc = convertToCell([0f0])
    zsrc = convertToCell([2*model.d[2]])

    # Set up source structure
    srcGeometry = Geometry(xsrc, ysrc, zsrc; dt=dt, t=time)

    # setup wavelet
    f0 = 0.015f0     # MHz
    wavelet = ricker_wavelet(time, dt, f0)
    q = judiVector(srcGeometry, wavelet)

    ntComp = get_computational_nt(srcGeometry, recGeometry, model)	
    info = Info(prod(model.n), nsrc, ntComp)

    return q, srcGeometry, recGeometry, info
end

### Process command line args
function parse_commandline()
    s = ArgParseSettings()
    @add_arg_table! s begin
        "--tti"
            help = "TTI, default False"
            action = :store_true
        "--fs"
            help = "Free surface, default False"
            action = :store_true
        "--nlayer", "-n"
            help = "Number of layers"
            arg_type = Int
            default = 3
    end
    return parse_args(s)
end
