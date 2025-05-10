pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE = 'chatops-website'
        DOCKER_TAG = "${BUILD_NUMBER}"
    }
    
    stages {
        stage('Build') {
            steps {
                echo 'Building website...'
                sh 'docker build -t ${DOCKER_IMAGE}:${DOCKER_TAG} .'
            }
        }
        
        stage('Test') {
            steps {
                echo 'Testing website...'
                sh '''
                    docker run -d -p 8080:80 --name test-${DOCKER_IMAGE} ${DOCKER_IMAGE}:${DOCKER_TAG}
                    sleep 5
                    curl -f http://localhost:8080 || exit 1
                    docker stop test-${DOCKER_IMAGE}
                    docker rm test-${DOCKER_IMAGE}
                '''
            }
        }
        
        stage('Deploy') {
            steps {
                echo 'Deploying website...'
                sh '''
                    # Stop and remove existing container if it exists
                    docker stop ${DOCKER_IMAGE} || true
                    docker rm ${DOCKER_IMAGE} || true
                    
                    # Run the new container
                    docker run -d -p 80:80 --name ${DOCKER_IMAGE} ${DOCKER_IMAGE}:${DOCKER_TAG}
                '''
            }
        }
    }
    
    post {
        always {
            echo 'Cleaning up...'
            sh 'docker system prune -f'
        }
        success {
            echo 'Deployment successful!'
        }
        failure {
            echo 'Deployment failed!'
        }
    }
} 