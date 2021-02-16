function gst = ur5FwdKin( q ) %renamed "joints" to "q" for convenience
% input: q is 6*1 vector where q(i) correspond to joint i in gazebo setting
% output: gst is 4*4 transformation matrix relative to base_link

    dims = size(q);

    if dims == [6 1]
        
        ur5Parameters
        
        %q = q - [0 -pi/2 0 -pi/2 0 0]';     %subtract encoder offset from joints

        gst = expm(wedge(xi1)*q(1)) * expm(wedge(xi2)*q(2)) * expm(wedge(xi3)*q(3)) ...
            * expm(wedge(xi4)*q(4)) * expm(wedge(xi5)*q(5)) * expm(wedge(xi6)*q(6)) ...
            * gst0;
        
    else
        error('Unrecognized dimensions on input. Expected 6x1, instead found %dx%d', dims(1), dims(2))
    end

end
