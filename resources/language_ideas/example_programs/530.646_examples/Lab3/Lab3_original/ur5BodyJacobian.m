function [ J ] = ur5BodyJacobian( q )
%ur5BodyJacobian computes the body jacobian of the ur5 at a given position
%   input: q is a 6x1 vector representing the joints of the ur5
%   output: J is a 6x6 matrix representing the current state's body jacobian
    
    dims = size(q);

    if dims == [6 1]
    
        %get initial twists of ur5 and other important parameters
        ur5Parameters

        %package twists into matrix so easy to access in loop
        xi = {xi1 xi2 xi3 xi4 xi5 xi6};
        
        g = gst0;
        
        J = zeros(6,6);
        
        %algorithm from mathematica to compute jacobian from twists/angles
        for i = 6:-1:1
            %rigid_inverse() is FINV renamed from lab1
            xi_prime = rigid_adjoint(rigid_inverse(g)) * xi{i};
            J(:,i) = xi_prime;
            
            g = expm(wedge(xi{i} * q(i))) * g;
        end
        
        
    else
        error('Unrecognized dimensions on input. Expected 6x1, instead found %dx%d', dims(1), dims(2))
    end
    
    
end

