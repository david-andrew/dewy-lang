function [ Adg ] = rigid_adjoint( g )
%rigid_adjoint computes the adjoint of the rigid body
%   input: g is a 4x4 rigid body transformation in homogeneous coordinates
%   output: Adg is the adjoint of g
%       i.e. Vs = Adg * Vb
    
    dims = size(g);
    
    if dims == [4 4]
        
        R = g(1:3,1:3);
        p = g(1:3,4);
        
        Adg = [R hat(p)*R; zeros(3,3) R];

    else
        error('Unrecognized dimensions on g. Expected 4x4, instead found %dx%d', dims(1), dims(2));
    end
    
end

