function [ xi ] = getXi( g )
%getXi extracts the twist coordinates from a homogeneous transform
%   inputs: g is a 4x4 homogeneous transformation matrix
%   outputs: xi is the 6x1 twist coordinates vector from g

    dims = size(g);
    
    if dims == [4 4]
        
        %%%%UNSTABLE, DO NOT USE%%%%
        %get the twist from the inverse of matrix exponential (matrix log)
        %xi_hat = logm(g);
        %xi = vee(xi_hat);
        
        
        %extract rotation and translation from g
        R = g(1:3,1:3);
        p = g(1:3, 4);
      
        %extract the axis w and angle t from the rotation matrix R
        r = vrrotmat2vec(R);
        w = r(1:3)';
        t = r(4);
            
       
        if abs(t) < epsilon
            %pure rotation
            xi = [p; zeros(3,1)];
        elseif norm(p) < epsilon
            %pure translation
            xi = [zeros(3,1); w*t];
        else
            %general twist
            A = (eye(3) - R) * hat(w) + (w*w'*t);
            v = inv(A) * p;
            xi = [v; w] * t;
        end

    else
        error('Unrecognized dimensions on g. Expected 4x4, instead found %dx%d', dims(1), dims(2));
    end

end

