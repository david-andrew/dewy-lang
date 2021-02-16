function [ J ] = ur5SpatialJacobian( q )
%ur5SpatialJacobian computes the spatial jacobian of the ur5 at a given position
%   input: q is a 6x1 vector representing the joints of the ur5
%   output: J is a 6x6 matrix representing the current state's spatial jacobian
    

    %prevent use because of incomplete implementation
    error('This function appears to be implemented incorrectly. It is currently disabled')

    dims = size(q);

    if dims == [6 1]
    
        ur5Parameters

        xi = [xi1 xi2 xi3 xi4 xi5 xi6];
        
        
        
        J = zeros(6,6);
        
        J(:,1) = xi(:,1);
        
        g = expm(wedge(xi(:,1)*q(1)));
        
    
        %algorithm from mathematica to compute jacobian from twists/angles
        for i = 2:6
            xi_prime = rigid_adjoint(g) * xi(:,i);
            J(:,i) = xi_prime;
            
            g = g * expm(wedge(xi(:,i) * q(i)));
        end
        
        
    else
        error('Unrecognized dimensions on input. Expected 6x1, instead found %dx%d', dims(1), dims(2))
    end
    
    
end