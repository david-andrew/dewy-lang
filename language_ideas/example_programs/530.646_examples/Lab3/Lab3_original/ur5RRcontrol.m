function [ finalerr ] = ur5RRcontrol( gdesired, K, ur5 )
%ur5Control is a discrete-time resolved rate controller for the ur5
%   inputs: 
%       gdesired is the 4x4 rigid transform to move the ur5 to (i.e. gst*)
%       K is the scalar gain applied to the controller
%       ur5 is the ur5_interface object which the controller will drive
%   outputs:
%       finalerr is the scalar final distance from the goal in cm.
%       -returns -1 if there is a failure (e.g. hit's a singularity)


    %error checking on inputs:
    %<insert error checking>
    
    %timer for if function takes too long
    tic

    %final twist compoents' norms which will complete the algorithm
    vf = 0.01;     %m (1 cm)
    wf = pi/24;     %radians (15 degrees)

    deltaT = 0.20;      %timestep
    frame_blank = 3;    %how many frames to skip operations during
    speed = 0.75;        %speed of ur5 relative to max allowable speed
    
    
    gdesired_inv = rigid_inverse(gdesired);  %inverse of goal position
    
    %keeps track of how many  loop iterations have occurred 
    loops = 0;
    
    
    %get current joint angles from ur5
    qk = force_get_current_joints(ur5);
    cur_q = qk;
    
        
    frame = tf_frame('base', 'control_path', ur5FwdKin(qk));
    pause(1)
    %END FOR TESTING SECTION
    
    
    %drive ur5 with controller
    while true
        loops = loops + 1;
        
        
        %qk = ur5.get_current_joints - ur5.home;
        %qk = qk_1
        
        xik = getXi(gdesired_inv * ur5FwdKin(qk));  %include joint offset from defined 0 at home position
        %vk = xik(1:3);
        %wk = xik(4:6);
    

        
        
        %check if the manipulability is good before proceeding 
        J = ur5BodyJacobian(qk);
        
        mu = [% all three manipulability measures
        
            manipulability(J, 'sigmamin')
            manipulability(J, 'detjac')
            manipulability(J, 'invcond')
        ];

        if norm(mu(3)) < 0.0001
            %near a singularity
            finalerr = -1;
            ur5.move_joints(ur5.home, 5)
            warning('UR5 is near a singularity. Resetting ur5 position and exiting RRcontroller.');
            return
        end
        
        if any(cur_q + ur5.home > pi-0.01) | any(cur_q + ur5.home <= -pi+0.01)
            %out of joint limits
            finalerr = -1;
            ur5.move_joints(ur5.home, 5)
            warning('UR5 is at its joint limit. Resetting ur5 position and exiting RRcontroller.');
            return
        end
        
        
        qk = qk - K*deltaT*inv(J)*xik;
        %+ ur5.home; %include joint offset from defined 0 at home position
        
        
        
        
        %command the arm to move according to the controller
        if mod(loops, frame_blank) == 0
            
            %check if task is completed based on the actial robot state
            cur_q = force_get_current_joints(ur5);
            cur_xik = getXi(gdesired_inv * ur5FwdKin(cur_q));  %include joint offset from defined 0 at home position
            vk = cur_xik(1:3);
            wk = cur_xik(4:6);
            if abs(norm(vk)) < vf & abs(norm(wk)) < wf
                finalerr = abs(norm(vk)*100);    % convert error from mm to cm
                return
            end
            
            
            
            
            %update frame visualization
            frame.move_frame('base', ur5FwdKin(qk));
            
            %max speed is pi/2 rad/s.
            %determine an interval which will not move too quickly
            interval = deltaT;
            
            
            cur_q = force_get_current_joints(ur5);
            delta_qk = qk - (cur_q - ur5.home);
            while norm(abs(delta_qk)/interval) > pi/2% ones(6,1)*pi/2
                interval = interval * 2;
            end
            interval = interval / speed;
            
            try
                ur5.move_joints(qk + ur5.home, interval);
            catch err
            end
                
            %pause(deltaT)
        end
        
        
        %if current attempt is taking to long, restart process
        if toc > 25
            finalerr = ur5RRcontrol(gdesired, K, ur5);
            return
        end

        
    end
        
        
end

